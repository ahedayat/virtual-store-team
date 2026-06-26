"""Sales and inventory context extraction, merge, and normalization for the Sales Agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.sales.empty_sales import extract_sales_summary, normalize_sales_summary
from agents.shared.schemas.base import AgentWarning

SALES_AGENT_NAME = "sales-agent"


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def extract_inventory(data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Extract inventory section from a context bundle or raw inventory payload."""
    if data is None:
        return None
    if not isinstance(data, Mapping):
        return None

    if "inventory" in data:
        section = data.get("inventory")
        return _coerce_mapping(section)

    if any(key in data for key in ("low_stock_count", "items")):
        return dict(data)

    return None


def normalize_inventory_summary(inventory: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize inventory shapes from Django API or coordinator bundles."""
    if inventory is None:
        return {"low_stock_count": 0, "items": []}

    items_raw = inventory.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(items_raw, list):
        items = [dict(item) for item in items_raw if isinstance(item, Mapping)]

    low_stock_count = inventory.get("low_stock_count")
    if not isinstance(low_stock_count, int) or isinstance(low_stock_count, bool):
        low_stock_count = len(items)

    normalized: dict[str, Any] = {
        "low_stock_count": low_stock_count,
        "items": items,
    }

    for key in ("generated_at", "store_id"):
        if key in inventory:
            normalized[key] = inventory[key]

    return normalized


def _inventory_item_key(item: Mapping[str, Any]) -> str | None:
    for key in ("sku", "product_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def merge_inventory_sections(
    base: Mapping[str, Any] | None,
    overlay: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge inventory sections with caller overlay winning on duplicate SKU/product keys."""
    merged = normalize_inventory_summary(base)
    overlay_normalized = normalize_inventory_summary(overlay)

    if not overlay_normalized["items"]:
        return merged

    index: dict[str, dict[str, Any]] = {}
    for item in merged["items"]:
        key = _inventory_item_key(item)
        if key is not None:
            index[key] = dict(item)

    for item in overlay_normalized["items"]:
        key = _inventory_item_key(item)
        if key is None:
            merged["items"].append(dict(item))
            continue
        index[key] = dict(item)

    merged["items"] = list(index.values())
    merged["low_stock_count"] = len(merged["items"])
    return merged


def merge_sales_analysis_context(
    *,
    django_context: Mapping[str, Any] | None = None,
    caller_context: Mapping[str, Any] | None = None,
    sales_summary: Mapping[str, Any] | None = None,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge Django-fetched and caller-supplied sales/inventory context deterministically.

    Merge rules:
    1. Django-fetched sections form the base when available.
    2. Explicit ``sales_summary`` or ``inventory`` arguments override bundle sections.
    3. Caller ``context`` overlays Django data:
       - ``sales_summary``: caller replaces the base section when present.
       - ``inventory``: items merge by SKU/product_id; caller wins duplicates.
       - Other top-level keys: caller wins.
    """
    merged: dict[str, Any] = {}

    if django_context is not None:
        merged.update(dict(django_context))

    caller = _coerce_mapping(caller_context)
    if caller is not None:
        if "sales_summary" in caller and caller.get("sales_summary") is not None:
            merged["sales_summary"] = dict(caller["sales_summary"])
        if "inventory" in caller and caller.get("inventory") is not None:
            merged["inventory"] = merge_inventory_sections(
                merged.get("inventory"),
                caller["inventory"],
            )
        for key, value in caller.items():
            if key in {"sales_summary", "inventory"}:
                continue
            merged[key] = value

    explicit_sales = _coerce_mapping(sales_summary)
    if explicit_sales is not None:
        merged["sales_summary"] = explicit_sales

    explicit_inventory = _coerce_mapping(inventory)
    if explicit_inventory is not None:
        merged["inventory"] = merge_inventory_sections(
            merged.get("inventory"),
            explicit_inventory,
        )

    if "sales_summary" in merged:
        normalized = normalize_sales_summary(merged["sales_summary"])
        if normalized is not None:
            merged["sales_summary"] = normalized

    if "inventory" in merged:
        merged["inventory"] = normalize_inventory_summary(merged["inventory"])

    return merged


def resolve_sales_run_context(
    *,
    context: Mapping[str, Any] | None = None,
    sales_summary: Mapping[str, Any] | None = None,
    inventory: Mapping[str, Any] | None = None,
    django_context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[AgentWarning]]:
    """Resolve the final sales analysis context and any fetch/merge warnings."""
    merged = merge_sales_analysis_context(
        django_context=django_context,
        caller_context=context,
        sales_summary=sales_summary,
        inventory=inventory,
    )
    return merged, []


def build_fetch_failure_warning(error_message: str) -> AgentWarning:
    return AgentWarning(
        code="django_fetch_failed",
        message=error_message,
    )
