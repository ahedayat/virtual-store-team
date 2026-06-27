"""Support Agent schemas (Phase 6.6 scaffold, Phase 9.1 approval policy, Phase 9.4 insights)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from agents.shared.schemas.base import BaseAgentResponse, StrictAgentModel

SupportPolicyCategory = Literal[
    "generic_faq",
    "product_question",
    "shipping_policy_question",
    "return_policy_question",
    "order_status_question",
    "refund_request",
    "cancellation_request",
    "address_change_request",
    "payment_issue",
    "order_dispute",
    "angry_or_escalated_customer",
    "legal_or_safety_claim",
    "sensitive_personal_data",
    "account_or_identity_issue",
    "unsupported_external_action",
    "unknown_or_ambiguous",
]

SupportRiskLevel = Literal["low", "medium", "high"]
SupportDefaultActionType = Literal["support.reply_draft", "support.escalate"]

SupportScopeStatus = Literal["in_scope", "approval_required", "out_of_scope"]

SupportRefusalCode = Literal[
    "sales_analysis_request",
    "marketing_or_content_request",
    "pricing_or_discount_request",
    "inventory_or_restock_request",
    "refund_or_payment_action",
    "order_mutation_request",
    "legal_or_medical_advice",
    "credential_or_secret_request",
    "direct_database_or_internal_api_request",
    "approval_bypass_request",
    "impersonate_other_agent_request",
    "system_prompt_disclosure_request",
    "instruction_override_request",
    "false_completion_instruction",
    "unknown_out_of_scope",
]


class SupportDraftSafetySignals(StrictAgentModel):
    """Draft safety flags used to gate auto-executable support reply classification."""

    includes_pii: bool = False
    includes_order_specific_facts: bool = False
    includes_refund_or_payment_promise: bool = False
    includes_policy_exception: bool = False
    requires_external_side_effect: bool = False
    includes_private_account_or_order_data: bool = False


class SupportApprovalPolicyDecision(StrictAgentModel):
    """Deterministic approval classification result for a support reply draft."""

    category: SupportPolicyCategory
    risk_level: SupportRiskLevel
    requires_approval: bool
    default_action_type: SupportDefaultActionType
    reason: str = Field(min_length=1)
    allowed_auto_executable: bool
    matched_policy_code: str = Field(min_length=1)


class SupportScopeEvaluation(StrictAgentModel):
    """Deterministic scope/refusal classification for a support customer message."""

    is_refusal: bool
    scope_status: SupportScopeStatus
    refusal_code: SupportRefusalCode | None = None
    reason: str = Field(min_length=1)
    safe_message: str = Field(min_length=1)
    suggested_next_step: str | None = None
    requires_approval: bool
    action_type: SupportDefaultActionType | None = None
    warnings: list[str] = Field(default_factory=list)
    support_category: SupportPolicyCategory | None = None


SupportSentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]


class SupportAggregateSentiment(StrictAgentModel):
    """Aggregate sentiment for a support analysis run (non-PII)."""

    label: SupportSentimentLabel
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SupportReplyDraft(StrictAgentModel):
    """Per-thread support reply draft with approval and safety metadata."""

    thread_ref: str = Field(min_length=1)
    reply_text: str = Field(min_length=1)
    action_type: SupportDefaultActionType
    requires_approval: bool
    risk_level: SupportRiskLevel
    matched_policy_code: str = Field(min_length=1)
    safety_notes: list[str] = Field(default_factory=list)
    reason: str | None = None
    rationale: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def validate_approval_metadata(self) -> Self:
        if self.action_type == "support.escalate" and not self.requires_approval:
            raise ValueError("support.escalate drafts must require manager approval")

        if self.risk_level == "high" and not self.requires_approval:
            raise ValueError("high-risk support drafts must require manager approval")

        return self


class SupportInsights(BaseAgentResponse):
    """Final Support Agent output contract with per-thread reply drafts."""

    summary: str = Field(min_length=1)
    themes: list[str] = Field(default_factory=list)
    sentiment: SupportAggregateSentiment
    reply_drafts: list[SupportReplyDraft] = Field(min_length=1)
    output_language: str | None = None


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
