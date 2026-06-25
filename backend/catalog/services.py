from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from catalog.models import Order, OrderItem, REVENUE_COUNTABLE_ORDER_STATUSES
from stores.models import Store


@dataclass(frozen=True)
class PeriodBounds:
    start: datetime
    end: datetime


def get_store_timezone(store: Store) -> ZoneInfo:
    try:
        return ZoneInfo(store.timezone)
    except Exception:
        return ZoneInfo("UTC")


def get_period_bounds(store: Store, reference: datetime | None = None) -> dict[str, PeriodBounds]:
    """Return timezone-aware UTC boundaries for today and the last 7 calendar days."""
    reference = reference or timezone.now()
    store_tz = get_store_timezone(store)
    local_now = reference.astimezone(store_tz)
    today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_local = today_start_local + timedelta(days=1)
    last_7_start_local = today_start_local - timedelta(days=6)

    return {
        "today": PeriodBounds(
            start=today_start_local.astimezone(dt_timezone.utc),
            end=today_end_local.astimezone(dt_timezone.utc),
        ),
        "last_7_days": PeriodBounds(
            start=last_7_start_local.astimezone(dt_timezone.utc),
            end=today_end_local.astimezone(dt_timezone.utc),
        ),
    }


def _average_order_value(total_revenue: Decimal, order_count: int) -> Decimal:
    if order_count == 0:
        return Decimal("0.00")
    return (total_revenue / order_count).quantize(Decimal("0.01"))


def _serialize_period(
    store: Store,
    bounds: PeriodBounds,
    *,
    top_products_limit: int = 5,
) -> dict:
    countable_orders = Order.objects.filter(
        tenant=store.tenant,
        store=store,
        status__in=REVENUE_COUNTABLE_ORDER_STATUSES,
        placed_at__gte=bounds.start,
        placed_at__lt=bounds.end,
    )

    order_count = countable_orders.count()
    total_revenue = countable_orders.aggregate(
        total=Sum("total_amount", default=Decimal("0.00"))
    )["total"]

    units_sold = (
        OrderItem.objects.filter(order__in=countable_orders).aggregate(
            total=Sum("quantity", default=0)
        )["total"]
        or 0
    )

    top_products_qs = (
        OrderItem.objects.filter(order__in=countable_orders)
        .values(
            "product_id",
            "product_name_snapshot",
            "sku_snapshot",
            "product__category__name",
        )
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("line_total"),
        )
        .order_by("-revenue", "-quantity_sold")[:top_products_limit]
    )

    top_products = [
        {
            "product_id": str(row["product_id"]),
            "name": row["product_name_snapshot"],
            "sku": row["sku_snapshot"],
            "quantity_sold": row["quantity_sold"],
            "revenue": row["revenue"],
            "category": row["product__category__name"] or None,
        }
        for row in top_products_qs
    ]

    return {
        "from": bounds.start.isoformat(),
        "to": bounds.end.isoformat(),
        "total_revenue": total_revenue,
        "order_count": order_count,
        "units_sold": units_sold,
        "average_order_value": _average_order_value(total_revenue, order_count),
        "top_products": top_products,
    }


def build_sales_summary(store: Store, reference: datetime | None = None) -> dict:
    """Build tenant/store-scoped sales summary for today and the last 7 days."""
    bounds = get_period_bounds(store, reference=reference)
    generated_at = (reference or timezone.now()).isoformat()

    return {
        "generated_at": generated_at,
        "store_id": str(store.id),
        "currency": store.currency,
        "periods": {
            "today": _serialize_period(store, bounds["today"]),
            "last_7_days": _serialize_period(store, bounds["last_7_days"]),
        },
    }
