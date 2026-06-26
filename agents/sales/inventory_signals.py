"""Inventory signal extraction for inventory-aware sales analysis."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.sales.empty_sales import extract_sales_summary, normalize_sales_summary
from agents.sales.sales_context import extract_inventory, normalize_inventory_summary


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _item_key(item: Mapping[str, Any]) -> str | None:
    for key in ("sku", "product_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _collect_top_products(sales_summary: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if sales_summary is None:
        return []

    normalized = normalize_sales_summary(sales_summary)
    if normalized is None:
        return []

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for period_key in ("last_7_days", "today"):
        period = normalized.get(period_key)
        if not isinstance(period, Mapping):
            continue
        top_products = period.get("top_products")
        if not isinstance(top_products, list):
            continue
        for item in top_products:
            if not isinstance(item, Mapping):
                continue
            key = _item_key(item)
            if key is None or key in seen:
                continue
            seen.add(key)
            collected.append(dict(item))

    return collected


def build_inventory_signals(
    *,
    inventory: Mapping[str, Any] | None,
    sales_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build structured inventory signals consumed by the sales analysis pipeline."""
    normalized_inventory = normalize_inventory_summary(inventory)
    top_products = _collect_top_products(sales_summary)

    sold_by_key: dict[str, dict[str, Any]] = {}
    for product in top_products:
        key = _item_key(product)
        if key is not None:
            sold_by_key[key] = product

    low_stock_products: list[dict[str, Any]] = []
    for item in normalized_inventory["items"]:
        signal_item = dict(item)
        signal_item["signal_type"] = "low_stock"
        low_stock_products.append(signal_item)

    slow_moving_products: list[dict[str, Any]] = []
    overstock_products: list[dict[str, Any]] = []

    top_keys = {_item_key(item) for item in top_products}
    top_keys.discard(None)

    for product in top_products:
        quantity_sold = _coerce_int(product.get("quantity_sold")) or 0
        key = _item_key(product)
        if key is None:
            continue
        if quantity_sold <= 1:
            slow_moving_products.append(
                {
                    **dict(product),
                    "signal_type": "slow_moving",
                    "quantity_sold": quantity_sold,
                }
            )

    for item in normalized_inventory["items"]:
        key = _item_key(item)
        if key is None or key in top_keys:
            continue
        available = _coerce_int(item.get("available_quantity"))
        threshold = _coerce_int(item.get("low_stock_threshold"))
        if available is None:
            continue
        if threshold is not None and available >= threshold * 2:
            overstock_products.append(
                {
                    **dict(item),
                    "signal_type": "overstock",
                }
            )

    return {
        "low_stock_products": low_stock_products,
        "slow_moving_products": slow_moving_products,
        "overstock_products": overstock_products,
        "promotion_eligible_products": slow_moving_products + overstock_products,
    }


def build_sales_analysis_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    """Assemble the structured payload passed to prompts and the mock LLM provider."""
    sales_summary = extract_sales_summary(context)
    inventory = extract_inventory(context)
    inventory_signals = build_inventory_signals(
        inventory=inventory,
        sales_summary=sales_summary,
    )

    payload: dict[str, Any] = {}
    if sales_summary is not None:
        payload.update(sales_summary)
    if inventory is not None:
        payload["inventory"] = normalize_inventory_summary(inventory)
    payload["inventory_signals"] = inventory_signals
    return payload
