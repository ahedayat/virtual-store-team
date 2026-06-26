"""Sales Agent structured response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agents.shared.schemas.base import BaseAgentResponse, StrictAgentModel

SalesActionType = Literal["sales.restock", "sales.discount", "sales.follow_up"]


class SalesRecommendation(StrictAgentModel):
    priority: int = Field(ge=1, le=5)
    action_type: SalesActionType
    title: str
    description: str
    rationale: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SalesAnalysisResult(BaseAgentResponse):
    summary: str
    insights: list[str] = Field(default_factory=list)
    recommendations: list[SalesRecommendation] = Field(default_factory=list)
