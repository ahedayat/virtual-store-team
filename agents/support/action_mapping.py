"""Map validated Support Agent reply drafts to Django-compatible action payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.shared.django_client import DjangoClient
from agents.shared.schemas.support import SupportInsights, SupportReplyDraft

SUPPORTED_SUPPORT_ACTION_TYPES = frozenset({"support.reply_draft", "support.escalate"})

_RISK_PRIORITY: dict[str, int] = {
    "high": 1,
    "medium": 3,
    "low": 4,
}
_DEFAULT_PRIORITY = 3


class SupportActionMappingError(ValueError):
    """Raised when a support reply draft cannot be mapped to a supported action payload."""


def _coerce_non_empty_string(value: Any) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _resolve_priority(risk_level: str) -> int:
    return _RISK_PRIORITY.get(risk_level, _DEFAULT_PRIORITY)


def _build_title(action_type: str) -> str:
    if action_type == "support.escalate":
        return "Support escalation review required"
    return "Support reply draft for manager review"


def _build_description(
    *,
    action_type: str,
    policy_code: str,
    reason: str | None,
    rationale: str | None,
) -> str:
    if action_type == "support.escalate":
        escalation_reason = reason or rationale
        if escalation_reason is not None:
            return f"Escalation draft for policy {policy_code}: {escalation_reason}"
        return f"Escalation draft for policy {policy_code}."

    draft_rationale = rationale or reason
    if draft_rationale is not None:
        return f"Reviewable reply draft for policy {policy_code}: {draft_rationale}"
    return f"Reviewable reply draft for policy {policy_code}."


def _is_low_risk_auto_eligible(
    *,
    action_type: str,
    risk_level: str,
    requires_approval: bool,
) -> bool:
    return (
        action_type == "support.reply_draft"
        and risk_level == "low"
        and not requires_approval
    )


def map_support_reply_draft_to_action_payload(
    draft: SupportReplyDraft | Mapping[str, Any],
    *,
    report_run_id: str | None = None,
) -> dict[str, Any]:
    """Convert a validated support reply draft into a Django internal action request body."""
    if isinstance(draft, SupportReplyDraft):
        action_type = draft.action_type
        thread_ref = draft.thread_ref
        reply_text = draft.reply_text
        requires_approval = draft.requires_approval
        risk_level = draft.risk_level
        policy_code = draft.matched_policy_code
        safety_notes = list(draft.safety_notes)
        reason = draft.reason
        rationale = draft.rationale
    else:
        action_type = draft.get("action_type")
        thread_ref = draft.get("thread_ref")
        reply_text = draft.get("reply_text")
        requires_approval = draft.get("requires_approval")
        risk_level = draft.get("risk_level")
        policy_code = draft.get("matched_policy_code")
        raw_safety_notes = draft.get("safety_notes", [])
        safety_notes = list(raw_safety_notes) if isinstance(raw_safety_notes, list) else []
        reason = draft.get("reason")
        rationale = draft.get("rationale")

    if action_type not in SUPPORTED_SUPPORT_ACTION_TYPES:
        raise SupportActionMappingError(
            f"Unsupported support action_type: {action_type!r}. "
            f"Allowed types: {sorted(SUPPORTED_SUPPORT_ACTION_TYPES)}."
        )

    resolved_thread_ref = _coerce_non_empty_string(thread_ref)
    if resolved_thread_ref is None:
        raise SupportActionMappingError("thread_ref is required for support action mapping.")

    if not isinstance(requires_approval, bool):
        raise SupportActionMappingError("requires_approval must be a boolean for support action mapping.")

    if risk_level not in {"low", "medium", "high"}:
        raise SupportActionMappingError("risk_level must be low, medium, or high for support action mapping.")

    resolved_policy_code = _coerce_non_empty_string(policy_code)
    if resolved_policy_code is None:
        raise SupportActionMappingError("matched_policy_code is required for support action mapping.")

    resolved_reason = _coerce_non_empty_string(reason)
    resolved_rationale = _coerce_non_empty_string(rationale)

    if action_type == "support.escalate":
        if requires_approval is not True:
            raise SupportActionMappingError("support.escalate drafts must require manager approval.")
        escalation_reason = resolved_reason or resolved_rationale
        if escalation_reason is None:
            raise SupportActionMappingError("reason is required for support.escalate action mapping.")

        inner_payload: dict[str, Any] = {
            "thread_ref": resolved_thread_ref,
            "reason": escalation_reason,
            "risk_level": risk_level,
            "policy_code": resolved_policy_code,
            "safety_notes": safety_notes,
            "source": "support-agent",
        }
    else:
        resolved_reply_text = _coerce_non_empty_string(reply_text)
        if resolved_reply_text is None:
            raise SupportActionMappingError("reply_text is required for support.reply_draft action mapping.")

        inner_payload = {
            "thread_ref": resolved_thread_ref,
            "reply_text": resolved_reply_text,
            "risk_level": risk_level,
            "policy_code": resolved_policy_code,
            "safety_notes": safety_notes,
            "source": "support-agent",
        }
        if _is_low_risk_auto_eligible(
            action_type=action_type,
            risk_level=risk_level,
            requires_approval=requires_approval,
        ):
            inner_payload["low_risk"] = True

    action_body: dict[str, Any] = {
        "action_type": action_type,
        "title": _build_title(action_type),
        "description": _build_description(
            action_type=action_type,
            policy_code=resolved_policy_code,
            reason=resolved_reason,
            rationale=resolved_rationale,
        ),
        "priority": _resolve_priority(risk_level),
        "requires_approval": requires_approval,
        "payload": inner_payload,
    }

    if report_run_id is not None and str(report_run_id).strip():
        action_body["report_run_id"] = str(report_run_id).strip()

    return action_body


def map_support_insights_to_actions(
    insights: SupportInsights,
    *,
    report_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Map all validated reply drafts in SupportInsights to action request bodies."""
    resolved_report_run_id = report_run_id
    if resolved_report_run_id is None:
        resolved_report_run_id = insights.metadata.report_run_id

    return [
        map_support_reply_draft_to_action_payload(
            draft,
            report_run_id=resolved_report_run_id,
        )
        for draft in insights.reply_drafts
    ]


def persist_support_actions(
    insights: SupportInsights,
    *,
    django_client: DjangoClient,
    report_run_id: str | None = None,
    agent_output_id: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Persist mapped support actions through Django internal APIs only.

    When ``dry_run`` is True, actions are mapped and returned without POSTing to Django.
    """
    action_bodies = map_support_insights_to_actions(
        insights,
        report_run_id=report_run_id,
    )

    if dry_run:
        return action_bodies

    persisted: list[dict[str, Any]] = []
    for action_body in action_bodies:
        request_body = dict(action_body)
        if agent_output_id is not None and "agent_output_id" not in request_body:
            request_body["agent_output_id"] = agent_output_id
        response = django_client.create_action(request_body)
        persisted.append(response)

    return persisted
