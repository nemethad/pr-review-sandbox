"""HTTP handlers. No SQL, no clock, no environment access."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.config import settings
from app.service import OrderService
from app.settings_cache import TenantSettingsCache


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


_settings_cache = TenantSettingsCache()


def get_tenant_settings(request: dict[str, Any], connection: Any) -> dict[str, Any]:
    tenant_id = require_tenant(request)

    def load(tid: str) -> dict[str, Any]:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT locale, currency FROM tenant_settings WHERE tenant_id = %s",
                (tid,),
            )
            row = cursor.fetchone()
        return {"locale": row[0], "currency": row[1]} if row else {}

    return {"status": 200, "body": _settings_cache.get(tenant_id, load)}
