"""Order business logic. Holds no database or clock of its own."""

from __future__ import annotations

from dataclasses import dataclass

from app.clock import Clock
from app.repository.orders import Order, OrderRepository

RETENTION_DAYS = 90


@dataclass(frozen=True)
class OrderView:
    id: str
    status: str
    total_cents: int
    age_days: int


class OrderService:
    def __init__(self, repository: OrderRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def _to_view(self, order: Order) -> OrderView:
        age = (self._clock.now() - order.created_at).days
        return OrderView(
            id=order.id,
            status=order.status,
            total_cents=order.total_cents,
            age_days=age,
        )

    def get_order(self, tenant_id: str, order_id: str) -> OrderView | None:
        order = self._repository.get(tenant_id, order_id)
        return self._to_view(order) if order else None

    def list_open_orders(self, tenant_id: str, limit: int) -> list[OrderView]:
        orders = self._repository.list_by_status(tenant_id, "open", limit)
        return [self._to_view(order) for order in orders]

    def is_expired(self, order: Order) -> bool:
        return (self._clock.now() - order.created_at).days > RETENTION_DAYS

    def list_by_filter(self, tenant_id: str, status: str, limit: int) -> list[OrderView]:
        orders = self._repository.list_filtered(tenant_id, status, limit)
        return [self._to_view(order) for order in orders]
