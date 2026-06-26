"""Generic shared schemas for agent structured responses."""

from pydantic import BaseModel, ConfigDict, Field


class StrictAgentModel(BaseModel):
    """Base model for agent responses with strict extra-field handling."""

    model_config = ConfigDict(extra="forbid")


class AgentWarning(StrictAgentModel):
    code: str
    message: str


class ScopeViolation(StrictAgentModel):
    requested_scope: str
    reason: str


class AgentResponseMetadata(StrictAgentModel):
    agent_name: str
    report_run_id: str | None = None


class BaseAgentResponse(StrictAgentModel):
    metadata: AgentResponseMetadata
    warnings: list[AgentWarning] = Field(default_factory=list)
