from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.utils import timezone

from django.db.models import F

from catalog.models import InventoryLevel, Order, OrderItem, REVENUE_COUNTABLE_ORDER_STATUSES
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


def _serialize_low_stock_item(inventory: InventoryLevel, *, available_quantity: int) -> dict:
    shortage_units = max(0, inventory.low_stock_threshold - available_quantity)
    reorder_target = inventory.reorder_target
    suggested_reorder_quantity = None
    if reorder_target is not None:
        suggested_reorder_quantity = max(0, reorder_target - available_quantity)

    product = inventory.product
    return {
        "product_id": str(product.id),
        "product_name": product.name,
        "sku": product.sku,
        "category": product.category.name if product.category_id else None,
        "quantity_on_hand": inventory.quantity_on_hand,
        "reserved_quantity": inventory.reserved_quantity,
        "available_quantity": available_quantity,
        "low_stock_threshold": inventory.low_stock_threshold,
        "shortage_units": shortage_units,
        "reorder_target": reorder_target,
        "suggested_reorder_quantity": suggested_reorder_quantity,
        "last_updated": inventory.updated_at.isoformat(),
    }


def build_low_stock_summary(store: Store, reference: datetime | None = None) -> dict:
    """Return products where available quantity is strictly below the low-stock threshold."""
    low_stock_qs = (
        InventoryLevel.objects.filter(
            tenant=store.tenant,
            store=store,
            is_active=True,
            product__is_active=True,
        )
        .select_related("product", "product__category")
        .annotate(available_qty=F("quantity_on_hand") - F("reserved_quantity"))
        .filter(available_qty__lt=F("low_stock_threshold"))
        .order_by("available_qty", "product__name")
    )

    items = [
        _serialize_low_stock_item(
            inventory,
            available_quantity=inventory.available_qty,
        )
        for inventory in low_stock_qs
    ]

    generated_at = (reference or timezone.now()).isoformat()

    return {
        "generated_at": generated_at,
        "store_id": str(store.id),
        "low_stock_count": len(items),
        "items": items,
    }
