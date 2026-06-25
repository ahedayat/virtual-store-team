from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from catalog.models import Product
from catalog.services import (
    build_low_stock_summary,
    build_recent_messages_summary,
    build_sales_summary,
)
from stores.models import Store
from tenants.models import Tenant

logger = logging.getLogger(__name__)

EMPTY_PRODUCTS = {"count": 0, "items": []}
EMPTY_SALES_SUMMARY = {"currency": None, "today": {}, "last_7_days": {}}
EMPTY_INVENTORY = {"low_stock_count": 0, "items": []}
EMPTY_MESSAGES = {"thread_count": 0, "threads": []}


def _serialize_product_summary(product: Product, *, currency: str) -> dict:
    category = None
    if product.category_id:
        category = {
            "id": str(product.category_id),
            "name": product.category.name,
            "slug": product.category.slug,
        }

    item = {
        "product_id": str(product.id),
        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "category": category,
        "price": product.price,
        "currency": currency,
        "is_active": product.is_active,
    }
    if product.metadata:
        item["metadata"] = product.metadata
    return item


def build_product_summary(store: Store) -> dict:
    """Return tenant/store-scoped active product summaries for AI consumption."""
    products = list(
        Product.objects.filter(
            tenant=store.tenant,
            store=store,
            is_active=True,
        )
        .select_related("category")
        .order_by("name")
    )
    items = [_serialize_product_summary(product, currency=store.currency) for product in products]
    return {
        "count": len(items),
        "items": items,
    }


def _map_sales_summary(raw: dict) -> dict:
    periods = raw.get("periods") or {}
    return {
        "currency": raw.get("currency"),
        "today": periods.get("today") or {},
        "last_7_days": periods.get("last_7_days") or {},
    }


def _map_inventory_summary(raw: dict) -> dict:
    return {
        "low_stock_count": raw.get("low_stock_count", 0),
        "items": raw.get("items") or [],
    }


def _map_messages_summary(raw: dict) -> dict:
    return {
        "thread_count": raw.get("thread_count", 0),
        "threads": raw.get("threads") or [],
    }


def _safe_section(
    section_name: str,
    builder,
    *,
    empty_value: dict,
    warnings: list[str],
) -> dict:
    try:
        return builder()
    except Exception:
        logger.exception(
            "Failed to build context bundle section",
            extra={"section": section_name},
        )
        warnings.append(f"{section_name} unavailable")
        return empty_value


def build_context_bundle(
    *,
    tenant: Tenant,
    store: Store,
    report_run_id: str,
    reference: datetime | None = None,
) -> dict:
    """Compose Phase 3 read services into a sanitized AI context bundle."""
    reference = reference or timezone.now()
    warnings: list[str] = []

    products = _safe_section(
        "products",
        lambda: build_product_summary(store),
        empty_value=EMPTY_PRODUCTS,
        warnings=warnings,
    )
    sales_summary = _safe_section(
        "sales_summary",
        lambda: _map_sales_summary(build_sales_summary(store, reference=reference)),
        empty_value={**EMPTY_SALES_SUMMARY, "currency": store.currency},
        warnings=warnings,
    )
    inventory = _safe_section(
        "inventory",
        lambda: _map_inventory_summary(build_low_stock_summary(store, reference=reference)),
        empty_value=EMPTY_INVENTORY,
        warnings=warnings,
    )
    messages = _safe_section(
        "messages",
        lambda: _map_messages_summary(build_recent_messages_summary(store, reference=reference)),
        empty_value=EMPTY_MESSAGES,
        warnings=warnings,
    )

    return {
        "report_run_id": str(report_run_id),
        "generated_at": reference.isoformat(),
        "tenant": {
            "id": str(tenant.id),
            "slug": tenant.slug,
            "name": tenant.name,
        },
        "store": {
            "id": str(store.id),
            "slug": store.slug,
            "name": store.name,
            "timezone": store.timezone,
            "currency": store.currency,
        },
        "products": products,
        "sales_summary": sales_summary,
        "inventory": inventory,
        "messages": messages,
        "warnings": warnings,
    }
