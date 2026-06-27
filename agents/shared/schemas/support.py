"""Support Agent schemas (Phase 6.6 scaffold, Phase 9.1 approval policy)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from agents.shared.schemas.base import StrictAgentModel

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
