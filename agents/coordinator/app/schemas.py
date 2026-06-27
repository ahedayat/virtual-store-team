"""Request and response models for coordinator workflow stubs."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from agents.shared.schemas.base import AgentWarning, StrictAgentModel


class ContextRef(StrictAgentModel):
    type: Literal["report_run"]
    id: UUID


class DailyReportJobRequest(StrictAgentModel):
    report_run_id: UUID
    tenant_id: UUID
    store_id: UUID
    context_ref: ContextRef
    request_id: str | None = None
    period: str | None = None
    requested_by: str | None = None

    @model_validator(mode="after")
    def validate_context_ref_alignment(self) -> "DailyReportJobRequest":
        if self.context_ref.id != self.report_run_id:
            raise ValueError("context_ref.id must match report_run_id.")
        return self


class DailyReportWorkflowResponse(StrictAgentModel):
    status: Literal["completed", "failed"]
    workflow: Literal["daily_report"]
    report_run_id: str
    message: str
    warnings: list[AgentWarning] = Field(default_factory=list)
    partial: bool = False

    @field_validator("report_run_id")
    @classmethod
    def report_run_id_must_be_uuid_string(cls, value: str) -> str:
        UUID(value)
        return value
