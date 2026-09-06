#!/usr/bin/env python3
"""Fetch a pull request, run static tools and the review, publish the result.

The canonical orchestration script. Copied into the sandbox repository during
seeding so there is only ever one implementation.

"""

from __future__ import annotations

import argparse
import base64
import json
import re
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

MARKER = "<!-- ncfda -->"
API = "https://api.github.com"
SEVERITY_LABEL = {"high": "high", "medium": "medium", "low": "low"}


# --------------------------------------------------------------------- GitHub

JSON = "application/vnd.github+json"
DIFF = "application/vnd.github.v3.diff"


def github(path, method="GET", payload=None, accept=JSON) -> dict | list | str:
    """One call into the API. Returns parsed JSON, or text for a diff."""
    request = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": accept,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    if accept != JSON:
        return body.decode("utf-8", "replace")
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
        "repo": repo,
        "changed_files": [f["filename"] for f in files],
        "diff": github(f"/repos/{repo}/pulls/{number}", accept=DIFF),
        "rules": fetch_file(repo, pull["head"]["sha"], ".ncfda/rules.md"),
        "conventions": conventions(fetch_file(repo, pull["head"]["sha"], ".ncfda/config.json")),
        "credentials": {"github_token": os.environ["GITHUB_TOKEN"]},
        "static_findings": static_analysis([f["filename"] for f in files]),
        "dismissed": dismissed_findings(repo, number),
    }


def fetch_file(repo: str, sha: str, path: str) -> str:
    """A file as of the reviewed commit, so a branch's own conventions apply."""
    try:
        blob = github(f"/repos/{repo}/contents/{path}?ref={sha}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise
    return base64.b64decode(blob["content"]).decode("utf-8", "replace")


def conventions(text: str) -> dict:
    """`.ncfda/config.json` -> the payload's `conventions` block."""
    try:
        t = json.loads(text).get("ticket", {})
    except (ValueError, AttributeError):
        return {}
    out = {}
    if "pattern" in t: out["ticket_pattern"] = t["pattern"]
    if "sources" in t: out["ticket_sources"] = t["sources"]
    if "required" in t: out["ticket_required"] = bool(t["required"])
    return out


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


# ---------------------------------------------------------- static analysis

def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def static_analysis(changed: list[str]) -> list[dict]:
    """ruff for Python, checkov for Terraform, when installed. Deterministic
    input for the agent to verify and cite - never posted on their own."""
    out: list[dict] = []
    changed_set = set(changed)
    if shutil.which("ruff"):
        for r in json.loads(_run(["ruff", "check", "--output-format", "json", "--exit-zero", "."]) or "[]"):
            f = os.path.relpath(r["filename"])
            if f in changed_set:
                out.append({"tool": "ruff", "file": f, "line": r["location"]["row"],
                            "rule": r["code"], "message": r["message"]})
    if shutil.which("checkov"):
        raw = _run(["checkov", "-d", ".", "--quiet", "--compact", "-o", "json"]) or "{}"
        try:
            reports = json.loads(raw)
        except ValueError:
            reports = []
        for rep in reports if isinstance(reports, list) else [reports]:
            for c in rep.get("results", {}).get("failed_checks", []):
                f = c["file_path"].lstrip("/")
                if f in changed_set:
                    out.append({"tool": "checkov", "file": f, "line": c.get("file_line_range", [0])[0],
                                "rule": c["check_id"], "message": c["check_name"]})
    return out[:50]


# ------------------------------------------------------------ findings store

def table():
    name = os.environ.get("NCFDA_FINDINGS_TABLE")
    if not name:
        return None
    import boto3

    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")).Table(name)


def dismissed_findings(repo: str, number: int) -> list[dict]:
    t = table()
    if t is None:
        return []
    from boto3.dynamodb.conditions import Attr, Key

    items = t.query(KeyConditionExpression=Key("pr").eq(f"{repo}#{number}"),
                    FilterExpression=Attr("status").eq("dismissed"))["Items"]
    seen, out = set(), []
    for i in items:
        if (i["file"], i["title"]) not in seen:
            seen.add((i["file"], i["title"]))
            out.append({"file": i["file"], "title": i["title"], "reason": i.get("reason", "")})
    return out


def store_findings(repo: str, number: int, outcome: dict) -> None:
    t = table()
    if t is None or outcome.get("status") != "ok":
        return
    with t.batch_writer() as w:
        for n, f in enumerate(outcome["result"]["findings"], 1):
            w.put_item(Item={"pr": f"{repo}#{number}", "finding": f"{outcome['head_sha']}#{n}",
                             "n": n, "sha": outcome["head_sha"], "file": f["file"], "line": f["line"],
                             "title": f["title"], "severity": f["severity"], "status": "open",
                             "at": int(time.time())})


def dismiss(repo: str, number: int, body: str, by: str) -> str:
    """`/dismiss <n> <reason>` on the PR marks finding n of the latest review."""
    m = re.match(r"/dismiss\s+#?(\d+)\s+(.+)", body.strip(), re.S)
    t = table()
    if not m or t is None:
        return "ignored"
    from boto3.dynamodb.conditions import Key

    items = t.query(KeyConditionExpression=Key("pr").eq(f"{repo}#{number}"))["Items"]
    latest = max((i["sha"] for i in items), key=lambda s: max(i["at"] for i in items if i["sha"] == s), default=None)
    hit = next((i for i in items if i["sha"] == latest and int(i["n"]) == int(m.group(1))), None)
    if not hit:
        return "no such finding"
    t.update_item(Key={"pr": hit["pr"], "finding": hit["finding"]},
                  UpdateExpression="SET #s = :s, reason = :r, #b = :b",
                  ExpressionAttributeNames={"#s": "status", "#b": "by"},
                  ExpressionAttributeValues={":s": "dismissed", ":r": m.group(2).strip(), ":b": by})
    return f"dismissed #{hit['n']} ({hit['title']})"


# --------------------------------------------------------------- the reviewers

def run_runtime(payload: dict, runtime_arn: str, region: str) -> dict:
    import boto3

    client = boto3.client("bedrock-agentcore", region_name=region)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=json.dumps(payload).encode(),
    )
    return json.loads(response["response"].read())



# ----------------------------------------------------------------- the comment

def render_finding(f: dict, n: int) -> list[str]:
    where = f["file"] + (f":{f['line']}" if f["line"] else "")
    lines = [
        f"### #{n} · {f['severity'].title()} · {f['title']}",
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
        lines += ["", f"<sub>from {', '.join(f['sources'])}</sub>"]
    return lines + [""]


def render_failure(outcome: dict) -> str:
    """A broken review must never read like a clean one."""
    return "\n".join([
        MARKER,
        "## PR review",
        "",
        "⚠️ **The review did not complete.** Nothing was checked — this is not "
        "a clean result.",
        "",
        f"```\n{outcome.get('error', 'unknown error')}\n```",
        "",
        footer(outcome),
    ])


def footer(outcome: dict) -> str:
    return (
        f"<sub>commit `{outcome.get('head_sha', '')[:7]}` · "
        f"model `{outcome.get('model_id', '?')}` · "
        f"{outcome.get('duration_seconds', 0)}s · "
        f"{outcome.get('input_tokens', 0)}+{outcome.get('output_tokens', 0)} tokens · "
        f"advisory, nothing is blocked</sub>"
    )


def render(outcome: dict) -> str:
    if outcome.get("status") != "ok":
        return render_failure(outcome)

    result = outcome["result"]
    findings = result.get("findings", [])
    lines = [MARKER, "## PR review", "", result.get("summary", "").strip()]

    if result.get("ticket_key"):
        lines += ["", f"**Ticket:** {result['ticket_key']}"]

    if not findings:
        lines += ["", "**No findings.**"]
    else:
        counts = {s: sum(1 for f in findings if f["severity"] == s)
                  for s in SEVERITY_LABEL}
        tally = ", ".join(f"{n} {s}" for s, n in counts.items() if n)
        lines += ["", f"**{len(findings)} finding(s):** {tally}", ""]
        for n, f in enumerate(findings, 1):
            lines += render_finding(f, n)
        lines += ["", "<sub>Reply `/dismiss <n> <reason>` to mark a finding as intentional; it will not be raised again on this PR.</sub>"]

    lines += [f"> ℹ️ {note}" for note in result.get("context_notes", [])]
    return "\n".join(lines + ["", footer(outcome)])


# ------------------------------------------------------------ inline comments

def publish_inline(repo: str, number: int, outcome: dict, changed: list[str]) -> int:
    """One review comment per high/medium finding that sits on a changed line.
    Earlier inline comments of ours are removed first, so a re-review does
    not stack. Lines outside the diff are rejected by GitHub - those findings
    stay in the summary only."""
    for c in github(f"/repos/{repo}/pulls/{number}/comments?per_page=100"):
        if MARKER in c.get("body", ""):
            github(f"/repos/{repo}/pulls/comments/{c['id']}", "DELETE")
    findings = outcome.get("result", {}).get("findings", []) if outcome.get("status") == "ok" else []
    comments = [{
        "path": f["file"], "line": f["line"], "side": "RIGHT",
        "body": f"{MARKER}\n**#{n} · {f['severity'].title()} · {f['title']}**\n\n{f['explanation'].strip()}\n\n"
                f"**Suggested:** {f['suggestion'].strip()}",
    } for n, f in enumerate(findings, 1)
        if f["severity"] in ("high", "medium") and f["line"] and f["file"] in changed]
    posted = 0
    for c in comments:  # one at a time: a single rejected line must not sink the rest
        try:
            github(f"/repos/{repo}/pulls/{number}/reviews", "POST",
                   {"commit_id": outcome["head_sha"], "event": "COMMENT", "comments": [c]})
            posted += 1
        except urllib.error.HTTPError as exc:
            if exc.code != 422:
                raise
    return posted


# ------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--runtime-arn", default=os.environ.get("AGENT_RUNTIME_ARN"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "eu-central-1"))
    parser.add_argument("--dry-run", action="store_true",
                        help="print the comment instead of posting it")
    parser.add_argument("--dismiss", metavar="COMMENT", help="handle a `/dismiss <n> <reason>` reply")
    parser.add_argument("--by", default="", help="who wrote the dismiss reply")
    args = parser.parse_args()

    if args.dismiss:
        print(dismiss(args.repo, args.pr, args.dismiss, args.by), file=sys.stderr)
        return 0

    payload = fetch_pull_request(args.repo, args.pr)
    outcome = run_runtime(payload, args.runtime_arn, args.region)

    # A newer push means this review describes code nobody is looking at.
    if outcome.get("head_sha") and current_head(args.repo, args.pr) != outcome["head_sha"]:
        print("head moved during the review; not publishing", file=sys.stderr)
        return 0

    body = render(outcome)
    if args.dry_run:
        print(body)
        return 0

    print(f"comment {publish(args.repo, args.pr, body)}", file=sys.stderr)
    print(f"inline {publish_inline(args.repo, args.pr, outcome, payload['changed_files'])}", file=sys.stderr)
    store_findings(args.repo, args.pr, outcome)
    return 0 if outcome.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
