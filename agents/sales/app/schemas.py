"""Request models for the Sales Agent HTTP API."""

from __future__ import annotations

from typing import Any

from agents.shared.schemas.base import StrictAgentModel


class SalesRunRequest(StrictAgentModel):
    context: dict[str, Any] | None = None
    sales_summary: dict[str, Any] | None = None
    inventory: dict[str, Any] | None = None
    store_id: str | None = None
    report_run_id: str | None = None
    output_language: str | None = None
    request_id: str | None = None
    fetch_from_django: bool = False
    persist_actions: bool = False
    dry_run: bool = False
    service_token: str | None = None
