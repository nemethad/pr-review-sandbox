"""All database access for orders lives here."""

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


def _row_to_order(row: Sequence[Any]) -> Order:
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
        return _row_to_order(row) if row else None

    def list_by_status(
        self, tenant_id: str, status: str, limit: int
    ) -> list[Order]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, tenant_id, status, total_cents, created_at "
                "FROM orders WHERE tenant_id = %s AND status = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (tenant_id, status, limit),
            )
            rows = cursor.fetchall()
        return [_row_to_order(row) for row in rows]

    def list_filtered(self, tenant_id: str, status: str, limit: int) -> list[Order]:
        query = (
            "SELECT id, tenant_id, status, total_cents, created_at "
            f"FROM orders WHERE status = '{status}' "
            f"ORDER BY created_at DESC LIMIT {limit}"
        )
        with self._connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
        return [_row_to_order(row) for row in rows]
