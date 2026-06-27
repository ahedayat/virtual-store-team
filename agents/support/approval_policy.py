"""Deterministic Support Agent approval classification policy table (Phase 9.1)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agents.shared.schemas.support import (
    SupportApprovalPolicyDecision,
    SupportDraftSafetySignals,
    SupportPolicyCategory,
)

SupportRiskLevel = Literal["low", "medium", "high"]
SupportDefaultActionType = Literal["support.reply_draft", "support.escalate"]

ALL_SUPPORT_POLICY_CATEGORIES: tuple[SupportPolicyCategory, ...] = (
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
)


@dataclass(frozen=True, slots=True)
class SupportPolicyTableEntry:
    """Code-level policy row for a support reply classification category."""

    policy_key: str
    category: SupportPolicyCategory
    risk_level: SupportRiskLevel
    base_requires_approval: bool
    default_action_type: SupportDefaultActionType
    allows_auto_when_safe: bool
    base_rationale: str


SUPPORT_APPROVAL_POLICY_TABLE: dict[str, SupportPolicyTableEntry] = {
    "generic_faq": SupportPolicyTableEntry(
        policy_key="generic_faq",
        category="generic_faq",
        risk_level="low",
        base_requires_approval=False,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=True,
        base_rationale="Generic FAQ replies may be auto-drafted when no unsafe draft signals are present.",
    ),
    "product_question": SupportPolicyTableEntry(
        policy_key="product_question",
        category="product_question",
        risk_level="low",
        base_requires_approval=False,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=True,
        base_rationale=(
            "Product availability or feature questions may be auto-drafted from sanitized catalog context only."
        ),
    ),
    "shipping_policy_question": SupportPolicyTableEntry(
        policy_key="shipping_policy_question",
        category="shipping_policy_question",
        risk_level="low",
        base_requires_approval=False,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=True,
        base_rationale="Shipping policy explanations are informational and may be auto-drafted when safe.",
    ),
    "return_policy_question": SupportPolicyTableEntry(
        policy_key="return_policy_question",
        category="return_policy_question",
        risk_level="medium",
        base_requires_approval=False,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=True,
        base_rationale=(
            "Return policy explanations are allowed without approval unless the draft approves a return "
            "or makes a policy exception."
        ),
    ),
    "order_status_question": SupportPolicyTableEntry(
        policy_key="order_status_question",
        category="order_status_question",
        risk_level="medium",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Order status replies involve account or order-specific facts and require manager review.",
    ),
    "refund_request": SupportPolicyTableEntry(
        policy_key="refund_request",
        category="refund_request",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Refund requests require manager approval before any customer-facing commitment.",
    ),
    "cancellation_request": SupportPolicyTableEntry(
        policy_key="cancellation_request",
        category="cancellation_request",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Cancellation requests may mutate orders and require manager approval.",
    ),
    "address_change_request": SupportPolicyTableEntry(
        policy_key="address_change_request",
        category="address_change_request",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Address changes require manager approval before any fulfillment mutation.",
    ),
    "payment_issue": SupportPolicyTableEntry(
        policy_key="payment_issue",
        category="payment_issue",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Payment issues are financially sensitive and require manager approval.",
    ),
    "order_dispute": SupportPolicyTableEntry(
        policy_key="order_dispute",
        category="order_dispute",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Order disputes require manager review before customer commitments.",
    ),
    "angry_or_escalated_customer": SupportPolicyTableEntry(
        policy_key="angry_or_escalated_customer",
        category="angry_or_escalated_customer",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.escalate",
        allows_auto_when_safe=False,
        base_rationale="Escalated or angry customer threads require human review before reply.",
    ),
    "legal_or_safety_claim": SupportPolicyTableEntry(
        policy_key="legal_or_safety_claim",
        category="legal_or_safety_claim",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.escalate",
        allows_auto_when_safe=False,
        base_rationale="Legal or safety-related claims must be escalated for manager review.",
    ),
    "sensitive_personal_data": SupportPolicyTableEntry(
        policy_key="sensitive_personal_data",
        category="sensitive_personal_data",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Replies involving sensitive personal data require manager approval.",
    ),
    "account_or_identity_issue": SupportPolicyTableEntry(
        policy_key="account_or_identity_issue",
        category="account_or_identity_issue",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Account or identity issues require manager approval before customer action.",
    ),
    "unsupported_external_action": SupportPolicyTableEntry(
        policy_key="unsupported_external_action",
        category="unsupported_external_action",
        risk_level="high",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Requests requiring unsupported external side effects require manager approval.",
    ),
    "unknown_or_ambiguous": SupportPolicyTableEntry(
        policy_key="unknown_or_ambiguous",
        category="unknown_or_ambiguous",
        risk_level="medium",
        base_requires_approval=True,
        default_action_type="support.reply_draft",
        allows_auto_when_safe=False,
        base_rationale="Unknown or ambiguous support requests default to manager approval.",
    ),
}

_UNSAFE_SIGNAL_FIELDS: tuple[str, ...] = (
    "includes_pii",
    "includes_order_specific_facts",
    "includes_refund_or_payment_promise",
    "includes_policy_exception",
    "requires_external_side_effect",
    "includes_private_account_or_order_data",
)

_UNSAFE_SIGNAL_REASONS: dict[str, str] = {
    "includes_pii": "draft includes PII",
    "includes_order_specific_facts": "draft includes order-specific facts",
    "includes_refund_or_payment_promise": "draft includes refund or payment promises",
    "includes_policy_exception": "draft includes a policy exception",
    "requires_external_side_effect": "draft requires an external side effect",
    "includes_private_account_or_order_data": "draft includes private account or order data",
}


def validate_support_policy_table() -> None:
    """Raise ValueError when the policy table is incomplete or inconsistent."""
    if len(SUPPORT_APPROVAL_POLICY_TABLE) != len(ALL_SUPPORT_POLICY_CATEGORIES):
        raise ValueError("Support policy table size does not match expected category count.")

    seen_policy_keys: set[str] = set()
    seen_categories: set[str] = set()

    for entry in SUPPORT_APPROVAL_POLICY_TABLE.values():
        if entry.policy_key in seen_policy_keys:
            raise ValueError(f"Duplicate support policy key: {entry.policy_key!r}.")
        seen_policy_keys.add(entry.policy_key)

        if entry.category in seen_categories:
            raise ValueError(f"Duplicate support policy category: {entry.category!r}.")
        seen_categories.add(entry.category)

        if entry.policy_key != entry.category:
            raise ValueError(
                f"Policy key {entry.policy_key!r} must match category {entry.category!r}."
            )

        if entry.policy_key not in SUPPORT_APPROVAL_POLICY_TABLE:
            raise ValueError(f"Policy table missing self-key for {entry.policy_key!r}.")

    missing = set(ALL_SUPPORT_POLICY_CATEGORIES) - seen_categories
    if missing:
        raise ValueError(f"Support policy table missing categories: {sorted(missing)}.")


def get_support_policy_entry(category: str) -> SupportPolicyTableEntry:
    """Return the policy row for a category, falling back to unknown_or_ambiguous."""
    normalized = category.strip() if isinstance(category, str) else ""
    if normalized in SUPPORT_APPROVAL_POLICY_TABLE:
        return SUPPORT_APPROVAL_POLICY_TABLE[normalized]
    return SUPPORT_APPROVAL_POLICY_TABLE["unknown_or_ambiguous"]


def _coerce_safety_signals(
    safety: SupportDraftSafetySignals | Mapping[str, Any] | None,
) -> SupportDraftSafetySignals:
    if safety is None:
        return SupportDraftSafetySignals()
    if isinstance(safety, SupportDraftSafetySignals):
        return safety
    return SupportDraftSafetySignals.model_validate(dict(safety))


def _active_unsafe_signals(safety: SupportDraftSafetySignals) -> list[str]:
    active: list[str] = []
    for field_name in _UNSAFE_SIGNAL_FIELDS:
        if getattr(safety, field_name) is True:
            active.append(field_name)
    return active


def evaluate_support_approval_policy(
    category: str,
    *,
    safety: SupportDraftSafetySignals | Mapping[str, Any] | None = None,
) -> SupportApprovalPolicyDecision:
    """Classify a support reply draft for auto-executable vs approval-required handling.

    Classification only — this helper does not execute actions or send messages.
    """
    entry = get_support_policy_entry(category)
    resolved_safety = _coerce_safety_signals(safety)
    unsafe_signals = _active_unsafe_signals(resolved_safety)

    if entry.base_requires_approval:
        requires_approval = True
        allowed_auto_executable = False
        reason = entry.base_rationale
    elif unsafe_signals:
        requires_approval = True
        allowed_auto_executable = False
        unsafe_reasons = ", ".join(_UNSAFE_SIGNAL_REASONS[name] for name in unsafe_signals)
        reason = f"{entry.base_rationale} Approval required because {unsafe_reasons}."
    else:
        requires_approval = False
        allowed_auto_executable = True
        reason = entry.base_rationale

    return SupportApprovalPolicyDecision(
        category=entry.category,
        risk_level=entry.risk_level,
        requires_approval=requires_approval,
        default_action_type=entry.default_action_type,
        reason=reason,
        allowed_auto_executable=allowed_auto_executable,
        matched_policy_code=entry.policy_key,
    )


validate_support_policy_table()
