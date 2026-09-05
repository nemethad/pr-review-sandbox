from datetime import datetime, timedelta, timezone

from app.clock import FrozenClock
from app.repository.orders import Order
from app.service import OrderService

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, orders):
        self._orders = orders

    def get(self, tenant_id, order_id):
        for order in self._orders:
            if order.tenant_id == tenant_id and order.id == order_id:
                return order
        return None

    def list_by_status(self, tenant_id, status, limit):
        return [
            o for o in self._orders
            if o.tenant_id == tenant_id and o.status == status
        ][:limit]


def make_order(order_id="o1", tenant="t1", days_old=3, status="open"):
    return Order(
        id=order_id,
        tenant_id=tenant,
        status=status,
        total_cents=1000,
        created_at=NOW - timedelta(days=days_old),
    )


def make_service(orders):
    return OrderService(FakeRepository(orders), FrozenClock(NOW))


def test_get_order_reports_age():
    service = make_service([make_order(days_old=3)])
    assert service.get_order("t1", "o1").age_days == 3


def test_get_order_is_tenant_scoped():
    service = make_service([make_order(tenant="t1")])
    assert service.get_order("t2", "o1") is None


def test_expired_after_retention_window():
    service = make_service([])
    assert service.is_expired(make_order(days_old=91)) is True
    assert service.is_expired(make_order(days_old=89)) is False
