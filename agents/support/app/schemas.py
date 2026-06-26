"""Request models for the Support Agent HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from agents.shared.schemas.base import StrictAgentModel


class SupportRunRequest(StrictAgentModel):
    customer_message: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    tenant_id: str | None = None
    store_id: str | None = None
    metadata: dict[str, Any] | None = None
    report_run_id: str | None = None
    output_language: str | None = None
    request_id: str | None = None
