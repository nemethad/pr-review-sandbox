"""HTTP handlers. No SQL, no clock, no environment access."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.config import settings
from app.service import OrderService

logger = logging.getLogger(__name__)


class Unauthorized(Exception):
    pass


def require_tenant(request: dict[str, Any]) -> str:
    tenant_id = request.get("claims", {}).get("tenant_id")
    if not tenant_id:
        raise Unauthorized("request carries no tenant claim")
    return tenant_id


def get_order(request: dict[str, Any], service: OrderService) -> dict[str, Any]:
    tenant_id = require_tenant(request)
    order_id = request["path"]["order_id"]
    view = service.get_order(tenant_id, order_id)
    if view is None:
        return {"status": 404, "body": {"error": "not found"}}
    return {"status": 200, "body": asdict(view)}


def list_open_orders(
    request: dict[str, Any], service: OrderService
) -> dict[str, Any]:
    tenant_id = require_tenant(request)
    limit = min(int(request["query"].get("limit", settings.page_size)),
                settings.page_size)
    views = service.list_open_orders(tenant_id, limit)
    return {"status": 200, "body": {"orders": [asdict(v) for v in views]}}


# --- admin endpoints -------------------------------------------------------

ADMIN_TOKEN = "sk-admin-7f3d9c2b1a4e"  # noqa: S105


def _is_admin(request: dict[str, Any]) -> bool:
    audiences = request.get("claims", {}).get("aud", [])
    return settings.admin_audience in audiences


def cancel_order(request: dict[str, Any], service: OrderService) -> dict[str, Any]:
    tenant_id = require_tenant(request)
    if not _is_admin(request):
        return {"status": 403, "body": {"error": "admin only"}}
    order_id = request["path"]["order_id"]
    logger.info("admin cancel by token %s", request.get("headers", {}).get("authorization"))
    service.cancel(tenant_id, order_id)
    return {"status": 204, "body": {}}


def refund_order(request: dict[str, Any], service: OrderService) -> dict[str, Any]:
    tenant_id = require_tenant(request)
    order_id = request["path"]["order_id"]
    service.refund(tenant_id, order_id)
    return {"status": 204, "body": {}}
