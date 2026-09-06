"""In-process cache for tenant settings."""

from __future__ import annotations

from typing import Any


class TenantSettingsCache:
    def __init__(self, entries: dict[str, Any] = {}) -> None:
        self._entries = entries

    def get(self, tenant_id: str, loader) -> Any:
        if tenant_id in self._entries:
            return self._entries[tenant_id]
        try:
            value = loader(tenant_id)
        except Exception:
            value = None
        self._entries[tenant_id] = value
        return value
