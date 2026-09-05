#!/usr/bin/env python3
"""Fetch a pull request, run the review, publish one sticky comment.

The canonical orchestration script. Copied into the sandbox repository during
seeding so there is only ever one implementation.

Runs the review two ways, chosen by --mode:
  runtime  invoke AgentCore Runtime (what the workflow does)
  local    import the agent and run it in this process (the baseline)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

MARKER = "<!-- prreview -->"
API = "https://api.github.com"
SEVERITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}


# --------------------------------------------------------------------- GitHub

def github(path: str, method: str = "GET", payload: dict | None = None) -> dict | list:
    request = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    return json.loads(body) if body else {}


def fetch_pull_request(repo: str, number: int) -> dict:
    pull = github(f"/repos/{repo}/pulls/{number}")
    files = github(f"/repos/{repo}/pulls/{number}/files?per_page=100")
    return {
        "title": pull["title"],
        "body": pull.get("body") or "",
        "branch": pull["head"]["ref"],
        "base_ref": pull["base"]["ref"],
        "head_sha": pull["head"]["sha"],
        "changed_files": [f["filename"] for f in files],
        "diff": fetch_diff(repo, number),
        "rules": fetch_rules(repo, pull["head"]["sha"]),
    }


def fetch_diff(repo: str, number: int) -> str:
    request = urllib.request.Request(
        f"{API}/repos/{repo}/pulls/{number}",
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github.v3.diff",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch_rules(repo: str, sha: str) -> str:
    """Rules as of the reviewed commit, so a branch's own conventions apply."""
    try:
        blob = github(f"/repos/{repo}/contents/.prreview/rules.md?ref={sha}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise
    import base64

    return base64.b64decode(blob["content"]).decode("utf-8", "replace")


def current_head(repo: str, number: int) -> str:
    return github(f"/repos/{repo}/pulls/{number}")["head"]["sha"]


def publish(repo: str, number: int, body: str) -> str:
    """Edit our own comment if it exists, otherwise post one."""
    comments = github(f"/repos/{repo}/issues/{number}/comments?per_page=100")
    for comment in comments:
        if MARKER in comment.get("body", ""):
            github(f"/repos/{repo}/issues/comments/{comment['id']}",
                   "PATCH", {"body": body})
            return "updated"
    github(f"/repos/{repo}/issues/{number}/comments", "POST", {"body": body})
    return "created"


# --------------------------------------------------------------- the reviewers

def run_runtime(payload: dict, runtime_arn: str, region: str) -> dict:
    import boto3

    client = boto3.client("bedrock-agentcore", region_name=region)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=json.dumps(payload).encode(),
    )
    return json.loads(response["response"].read())


def run_local(payload: dict) -> dict:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent", "src"))
    from prreview_agent.agent import review

    return review(**payload).model_dump(mode="json")


# ----------------------------------------------------------------- the comment

def render(outcome: dict, repo: str, number: int) -> str:
    head = outcome.get("head_sha", "")[:7]
    lines = [MARKER, "## PR review"]

    if outcome.get("status") != "ok":
        lines += [
            "",
            f"⚠️ **The review did not complete.** Nothing below was checked — this is "
            f"not a clean result.",
            "",
            f"```\n{outcome.get('error', 'unknown error')}\n```",
            "",
            f"<sub>commit `{head}` · model `{outcome.get('model_id', '?')}`</sub>",
        ]
        return "\n".join(lines)

    result = outcome["result"]
    findings = result.get("findings", [])

    lines += ["", result.get("summary", "").strip()]

    if result.get("ticket_key"):
        lines.append(f"\n**Ticket:** {result['ticket_key']}")

    if not findings:
        lines += ["", "**No findings.**"]
    else:
        counts = {}
        for f in findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        tally = ", ".join(
            f"{counts[s]} {SEVERITY_LABEL[s].lower()}"
            for s in ("high", "medium", "low") if s in counts
        )
        lines += ["", f"**{len(findings)} finding(s):** {tally}", ""]
        for f in findings:
            where = f["file"] + (f":{f['line']}" if f["line"] else "")
            lines += [
                f"### {SEVERITY_LABEL[f['severity']]} · {f['title']}",
                f"`{where}` · {f['category'].replace('_', ' ')} · "
                f"confidence {f['confidence']:.0%}",
                "",
                f["explanation"].strip(),
                "",
                f"**Suggested:** {f['suggestion'].strip()}",
            ]
            if f.get("evidence"):
                lines += ["", "```", f["evidence"].strip(), "```"]
            if f.get("sources"):
                lines.append(f"\n<sub>from {', '.join(f['sources'])}</sub>")
            lines.append("")

    for note in result.get("context_notes", []):
        lines.append(f"> ℹ️ {note}")

    lines += [
        "",
        f"<sub>commit `{head}` · model `{outcome.get('model_id', '?')}` · "
        f"{outcome.get('duration_seconds', 0)}s · "
        f"{outcome.get('input_tokens', 0)}+{outcome.get('output_tokens', 0)} tokens · "
        f"advisory, nothing is blocked</sub>",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--mode", choices=("runtime", "local"), default="runtime")
    parser.add_argument("--runtime-arn", default=os.environ.get("AGENT_RUNTIME_ARN"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-central-1"))
    parser.add_argument("--dry-run", action="store_true",
                        help="print the comment instead of posting it")
    args = parser.parse_args()

    payload = fetch_pull_request(args.repo, args.pr)
    outcome = (
        run_local(payload)
        if args.mode == "local"
        else run_runtime(payload, args.runtime_arn, args.region)
    )

    # A newer push means this review describes code nobody is looking at.
    if outcome.get("head_sha") and current_head(args.repo, args.pr) != outcome["head_sha"]:
        print("head moved during the review; not publishing", file=sys.stderr)
        return 0

    body = render(outcome, args.repo, args.pr)
    if args.dry_run:
        print(body)
        return 0

    print(f"comment {publish(args.repo, args.pr, body)}", file=sys.stderr)
    return 0 if outcome.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
