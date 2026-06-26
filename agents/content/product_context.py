"""Product context extraction and normalization for the Content Agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CONTENT_AGENT_NAME = "content-agent"


def _coerce_non_empty_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def normalize_product(product: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a product record into the Content Agent context shape."""
    normalized: dict[str, Any] = {}

    product_id = _coerce_non_empty_string(product.get("product_id")) or _coerce_non_empty_string(
        product.get("id")
    )
    if product_id:
        normalized["product_id"] = product_id

    title = _coerce_non_empty_string(product.get("title")) or _coerce_non_empty_string(
        product.get("name")
    )
    if title:
        normalized["title"] = title

    category = _coerce_non_empty_string(product.get("category")) or _coerce_non_empty_string(
        product.get("category_name")
    )
    if category:
        normalized["category"] = category

    price = product.get("price")
    if price is not None and price != "":
        normalized["price"] = price

    currency = _coerce_non_empty_string(product.get("currency"))
    if currency:
        normalized["currency"] = currency

    image_url = _coerce_non_empty_string(product.get("image_url")) or _coerce_non_empty_string(
        product.get("image")
    )
    if image_url:
        normalized["image_url"] = image_url

    sku = _coerce_non_empty_string(product.get("sku"))
    if sku:
        normalized["sku"] = sku

    return normalized


def extract_products(data: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Extract and normalize products from a context bundle or products list."""
    if data is None:
        return []

    if isinstance(data, list):
        products_raw = data
    elif isinstance(data, Mapping):
        if "products" in data:
            products_raw = data.get("products")
        else:
            return []
    else:
        return []

    if not isinstance(products_raw, list):
        return []

    normalized_products: list[dict[str, Any]] = []
    for item in products_raw:
        if not isinstance(item, Mapping):
            continue
        product = normalize_product(item)
        if product:
            normalized_products.append(product)

    return normalized_products


def extract_store_context(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract store context from a coordinator bundle or explicit store mapping."""
    if data is None or not isinstance(data, Mapping):
        return {}

    if "store" in data and isinstance(data.get("store"), Mapping):
        return dict(data["store"])

    store_context: dict[str, Any] = {}
    for key in ("id", "slug", "name", "display_name", "currency", "timezone", "settings"):
        if key in data:
            store_context[key] = data[key]

    return store_context


def extract_campaign_angle(data: Mapping[str, Any] | None) -> str | None:
    if data is None or not isinstance(data, Mapping):
        return None
    return _coerce_non_empty_string(data.get("campaign_angle"))


def is_empty_products_context(products: list[Mapping[str, Any]] | None) -> bool:
    """Return True when no usable product records are available."""
    if not products:
        return True
    return all(not normalize_product(product) for product in products)


def resolve_content_run_context(
    *,
    context: Mapping[str, Any] | None = None,
    products: list[Mapping[str, Any]] | None = None,
    store_context: Mapping[str, Any] | None = None,
    campaign_angle: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    """Resolve products, store context, and campaign angle from explicit args or bundle."""
    resolved_products = extract_products(products) if products is not None else []
    resolved_store = dict(store_context) if store_context is not None else {}
    resolved_campaign_angle = _coerce_non_empty_string(campaign_angle)

    if context is not None and isinstance(context, Mapping):
        if not resolved_products:
            resolved_products = extract_products(context)
        if not resolved_store:
            resolved_store = extract_store_context(context)
        if resolved_campaign_angle is None:
            resolved_campaign_angle = extract_campaign_angle(context)

    return resolved_products, resolved_store, resolved_campaign_angle
