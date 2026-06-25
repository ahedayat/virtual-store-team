from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from catalog.models import Order, OrderItem, REVENUE_ELIGIBLE_ORDER_STATUSES
from stores.models import Store

TOP_PRODUCTS_LIMIT = 5
MONEY_QUANTIZE = Decimal("0.01")


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def _format_money(value: Decimal) -> str:
    return format(_quantize_money(value), "f")


def _store_timezone(store: Store) -> ZoneInfo:
    try:
        return ZoneInfo(store.timezone)
    except Exception:
        return ZoneInfo("UTC")


def _period_bounds(
    store: Store,
    *,
    start_day_offset: int,
    end_day_offset: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return [start, end) bounds in UTC for store-local calendar day offsets.

    ``start_day_offset`` and ``end_day_offset`` are relative to the store's
    current local calendar day (0 = today). ``end_day_offset`` is inclusive
    for the last local day included in the range.
    """
    tz = _store_timezone(store)
    local_now = (now or timezone.now()).astimezone(tz)
    local_today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = local_today_start + timedelta(days=start_day_offset)
    period_end = local_today_start + timedelta(days=end_day_offset + 1)
    return period_start.astimezone(timezone.utc), period_end.astimezone(timezone.utc)


def _eligible_orders_queryset(store: Store, period_start, period_end):
    return Order.objects.filter(
        tenant_id=store.tenant_id,
        store_id=store.id,
        status__in=REVENUE_ELIGIBLE_ORDER_STATUSES,
        placed_at__gte=period_start,
        placed_at__lt=period_end,
    )


def _aggregate_period(store: Store, period_start, period_end) -> dict:
    orders = _eligible_orders_queryset(store, period_start, period_end)
    order_stats = orders.aggregate(
        total_revenue=Sum("total_amount"),
        order_count=Count("id"),
    )
    total_revenue = order_stats["total_revenue"] or Decimal("0.00")
    order_count = order_stats["order_count"] or 0

    item_stats = OrderItem.objects.filter(
        tenant_id=store.tenant_id,
        store_id=store.id,
        order__status__in=REVENUE_ELIGIBLE_ORDER_STATUSES,
        order__placed_at__gte=period_start,
        order__placed_at__lt=period_end,
    ).aggregate(units_sold=Sum("quantity"))
    units_sold = item_stats["units_sold"] or 0

    if order_count:
        average_order_value = _quantize_money(total_revenue / order_count)
    else:
        average_order_value = Decimal("0.00")

    top_products = _top_products_for_period(store, period_start, period_end)

    return {
        "from": period_start.isoformat(),
        "to": period_end.isoformat(),
        "total_revenue": _format_money(total_revenue),
        "order_count": order_count,
        "units_sold": units_sold,
        "average_order_value": _format_money(average_order_value),
        "top_products": top_products,
    }


def _top_products_for_period(store: Store, period_start, period_end) -> list[dict]:
    rows = (
        OrderItem.objects.filter(
            tenant_id=store.tenant_id,
            store_id=store.id,
            order__status__in=REVENUE_ELIGIBLE_ORDER_STATUSES,
            order__placed_at__gte=period_start,
            order__placed_at__lt=period_end,
        )
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
        .order_by("-revenue", "-quantity_sold")[:TOP_PRODUCTS_LIMIT]
    )

    top_products = []
    for row in rows:
        entry = {
            "product_id": str(row["product_id"]),
            "name": row["product_name_snapshot"],
            "sku": row["sku_snapshot"],
            "quantity_sold": row["quantity_sold"] or 0,
            "revenue": _format_money(row["revenue"] or Decimal("0.00")),
        }
        category_name = row["product__category__name"]
        if category_name:
            entry["category"] = category_name
        top_products.append(entry)
    return top_products


def build_sales_summary(store: Store, *, now: datetime | None = None) -> dict:
    """Build timezone-aware sales summary for today and the last 7 days."""
    today_start, today_end = _period_bounds(store, start_day_offset=0, end_day_offset=0, now=now)
    last_7_start, last_7_end = _period_bounds(
        store,
        start_day_offset=-6,
        end_day_offset=0,
        now=now,
    )

    generated_at = (now or timezone.now()).astimezone(timezone.utc)

    return {
        "generated_at": generated_at.isoformat(),
        "store_id": str(store.id),
        "currency": store.currency,
        "periods": {
            "today": _aggregate_period(store, today_start, today_end),
            "last_7_days": _aggregate_period(store, last_7_start, last_7_end),
        },
    }
