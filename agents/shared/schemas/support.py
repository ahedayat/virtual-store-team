"""Support Agent scaffold response schema (Phase 6.6)."""

from __future__ import annotations

from pydantic import Field

from agents.shared.schemas.base import StrictAgentModel


class SupportRunResponse(StrictAgentModel):
    """Structured mock support reply for Phase 6 scaffold endpoints."""

    agent: str = Field(default="support-agent")
    status: str
    language: str
    reply: str
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
    request_id: str | None = None
