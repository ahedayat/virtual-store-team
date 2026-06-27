"""Shared Pydantic schemas and validation utilities for agent responses."""

from agents.shared.schemas.base import (
    AgentResponseMetadata,
    AgentWarning,
    BaseAgentResponse,
    ScopeViolation,
    StrictAgentModel,
)
from agents.shared.schemas.errors import (
    AgentSchemaConfigurationError,
    AgentSchemaError,
    AgentSchemaValidationError,
)
from agents.shared.schemas.content import ContentDraft, ContentSuggestions
from agents.shared.schemas.sales import SalesAnalysisResult, SalesRecommendation
from agents.shared.schemas.support import (
    SupportApprovalPolicyDecision,
    SupportDraftSafetySignals,
    SupportRunResponse,
)
from agents.shared.schemas.validation import export_json_schema, validate_agent_response

__all__ = [
    "ContentDraft",
    "ContentSuggestions",
    "AgentResponseMetadata",
    "AgentSchemaConfigurationError",
    "AgentSchemaError",
    "AgentSchemaValidationError",
    "AgentWarning",
    "BaseAgentResponse",
    "SalesAnalysisResult",
    "SalesRecommendation",
    "ScopeViolation",
    "StrictAgentModel",
    "SupportApprovalPolicyDecision",
    "SupportDraftSafetySignals",
    "SupportRunResponse",
    "export_json_schema",
    "validate_agent_response",
]
