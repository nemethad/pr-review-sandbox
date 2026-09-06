"""One structured line per request.

Bodies, headers and token material are never logged; see the logging
conventions page. Duration comes from the injected clock so tests can assert
on it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.clock import Clock

logger = logging.getLogger("orders.request")


def log_request(
    *,
    method: str,
    route: str,
    status: int,
    tenant_id: str,
    request_id: str,
    duration_ms: int,
) -> None:
    logger.info(
        json.dumps(
            {
                "method": method,
                "route": route,
                "status": status,
                "tenant_id": tenant_id,
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
            sort_keys=True,
        )
    )


def observe(handler, clock: Clock, route: str):
    """Wrap a handler so every call emits exactly one log line."""

    def wrapped(request: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        started = clock.now()
        response = handler(request, *args, **kwargs)
        elapsed_ms = int((clock.now() - started).total_seconds() * 1000)
        log_request(
            method=request.get("method", "GET"),
            route=route,
            status=response.get("status", 0),
            tenant_id=request.get("claims", {}).get("tenant_id", ""),
            request_id=request.get("request_id", ""),
            duration_ms=elapsed_ms,
        )
        return response

    return wrapped
