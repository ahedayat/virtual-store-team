"""Request models for the Content Agent HTTP API."""

from __future__ import annotations

from typing import Any

from agents.shared.schemas.base import StrictAgentModel


class ContentRunRequest(StrictAgentModel):
    context: dict[str, Any] | None = None
    products: list[dict[str, Any]] | None = None
    store_context: dict[str, Any] | None = None
    campaign_angle: str | None = None
    report_run_id: str | None = None
    output_language: str | None = None
    max_drafts_per_run: int | None = None
    request_id: str | None = None
