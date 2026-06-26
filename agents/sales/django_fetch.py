"""Fetch sales and inventory context from Django internal APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.sales.empty_sales import normalize_sales_summary
from agents.sales.sales_context import (
    build_fetch_failure_warning,
    normalize_inventory_summary,
)
from agents.shared.django_client import DjangoClient
from agents.shared.django_client.errors import DjangoClientError
from agents.shared.schemas.base import AgentWarning


def _map_sales_summary_response(raw: Mapping[str, Any]) -> dict[str, Any]:
    periods = raw.get("periods") or {}
    mapped = {
        "currency": raw.get("currency"),
        "today": dict(periods.get("today") or {}),
        "last_7_days": dict(periods.get("last_7_days") or {}),
    }
    normalized = normalize_sales_summary(mapped)
    return normalized if normalized is not None else mapped


def _map_inventory_response(raw: Mapping[str, Any]) -> dict[str, Any]:
    return normalize_inventory_summary(raw)


def fetch_sales_context_from_django(
    django_client: DjangoClient,
    store_id: str,
) -> dict[str, Any]:
    """Fetch sales summary and low-stock inventory for a store from Django."""
    sales_raw = django_client.get_sales_summary(store_id)
    inventory_raw = django_client.get_low_stock_inventory(store_id)

    return {
        "store_id": store_id,
        "sales_summary": _map_sales_summary_response(sales_raw),
        "inventory": _map_inventory_response(inventory_raw),
        "django_fetched": True,
    }


def fetch_sales_context_with_fallback(
    *,
    django_client: DjangoClient | None,
    store_id: str | None,
    fetch_from_django: bool,
) -> tuple[dict[str, Any] | None, list[AgentWarning]]:
    """Fetch Django context or return ``None`` with a warning when fetch fails."""
    if not fetch_from_django:
        return None, []

    if django_client is None:
        return None, [
            build_fetch_failure_warning(
                "Django fetch requested but no Django client was configured."
            )
        ]

    if store_id is None or not str(store_id).strip():
        return None, [
            build_fetch_failure_warning(
                "Django fetch requested but store_id was not provided."
            )
        ]

    try:
        return fetch_sales_context_from_django(django_client, str(store_id).strip()), []
    except DjangoClientError as exc:
        return None, [build_fetch_failure_warning(str(exc))]
