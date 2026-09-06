"""Repository for orders.

Every public method takes the tenant first; every query filters on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence


@dataclass(frozen=True)
class Order:
    id: str
    tenant_id: str
    status: str
    total_cents: int
    created_at: datetime


def _map_row(row: Sequence[Any]) -> Order:
    """Column order matches every SELECT in this module."""
    return Order(
        id=row[0],
        tenant_id=row[1],
        status=row[2],
        total_cents=row[3],
        created_at=row[4],
    )


class OrderRepository:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def get(self, tenant_id: str, order_id: str) -> Order | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, tenant_id, status, total_cents, created_at "
                "FROM orders WHERE tenant_id = %s AND id = %s",
                (tenant_id, order_id),
            )
            row = cursor.fetchone()
        return _map_row(row) if row else None

    def list_by_status(
        self, tenant_id: str, status: str, limit: int
    ) -> list[Order]:
        """Newest first. `limit` is already capped by the handler."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, tenant_id, status, total_cents, created_at "
                "FROM orders WHERE status = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (status, limit),
            )
            rows = cursor.fetchall()
        return [_map_row(row) for row in rows]
