"""Content Agent structured response schemas."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from agents.shared.schemas.base import BaseAgentResponse, StrictAgentModel

ContentActionType = Literal["content.instagram_draft", "content.product_description"]


class ContentDraft(StrictAgentModel):
    action_type: ContentActionType
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    draft_text: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    product_id: str | None = None
    campaign_angle: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    requires_approval: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    output_language: str | None = None

    @model_validator(mode="after")
    def validate_content_draft_rules(self) -> Self:
        if self.action_type == "content.product_description":
            if not self.product_id or not self.product_id.strip():
                raise ValueError(
                    "product_id is required for content.product_description drafts"
                )

        if self.requires_approval is False:
            raise ValueError(
                "content suggestions must require manager approval before external use"
            )

        return self


class ContentSuggestions(BaseAgentResponse):
    summary: str = Field(min_length=1)
    drafts: list[ContentDraft] = Field(default_factory=list)
    output_language: str | None = None
