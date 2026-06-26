"""Map validated Content Agent drafts to Django-compatible approval-required actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.content.prompts import ALLOWED_CONTENT_ACTION_TYPES
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.content import ContentDraft, ContentSuggestions

SUPPORTED_CONTENT_ACTION_TYPES = frozenset(ALLOWED_CONTENT_ACTION_TYPES)
DEFAULT_CONTENT_ACTION_PRIORITY = 3


class ContentActionMappingError(ValueError):
    """Raised when a content draft cannot be mapped to a supported action payload."""


def map_content_draft_to_action_payload(
    draft: ContentDraft | Mapping[str, Any],
    *,
    report_run_id: str | None = None,
) -> dict[str, Any]:
    """Convert a validated content draft into a Django internal action request body."""
    if isinstance(draft, ContentDraft):
        action_type = draft.action_type
        title = draft.title
        description = draft.description
        draft_text = draft.draft_text
        rationale = draft.rationale
        product_id = draft.product_id
        campaign_angle = draft.campaign_angle
        priority = draft.priority
        draft_payload = dict(draft.payload)
        output_language = draft.output_language
    else:
        action_type = draft.get("action_type")
        title = draft.get("title")
        description = draft.get("description")
        draft_text = draft.get("draft_text")
        rationale = draft.get("rationale")
        product_id = draft.get("product_id")
        campaign_angle = draft.get("campaign_angle")
        priority = draft.get("priority")
        raw_payload = draft.get("payload", {})
        draft_payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
        output_language = draft.get("output_language")

    if action_type not in SUPPORTED_CONTENT_ACTION_TYPES:
        raise ContentActionMappingError(
            f"Unsupported content action_type: {action_type!r}. "
            f"Allowed types: {sorted(SUPPORTED_CONTENT_ACTION_TYPES)}."
        )

    if not isinstance(title, str) or not title.strip():
        raise ContentActionMappingError("title is required for content action mapping.")
    if not isinstance(description, str) or not description.strip():
        raise ContentActionMappingError("description is required for content action mapping.")
    if not isinstance(draft_text, str) or not draft_text.strip():
        raise ContentActionMappingError("draft_text is required for content action mapping.")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ContentActionMappingError("rationale is required for content action mapping.")

    resolved_priority = priority if isinstance(priority, int) and not isinstance(priority, bool) else DEFAULT_CONTENT_ACTION_PRIORITY

    inner_payload: dict[str, Any] = dict(draft_payload)
    inner_payload["draft_text"] = draft_text.strip()
    inner_payload["rationale"] = rationale.strip()

    if isinstance(product_id, str) and product_id.strip():
        inner_payload["product_id"] = product_id.strip()
    elif action_type == "content.product_description":
        raise ContentActionMappingError(
            "product_id is required for content.product_description action mapping."
        )

    if isinstance(campaign_angle, str) and campaign_angle.strip():
        inner_payload["campaign_angle"] = campaign_angle.strip()

    if isinstance(output_language, str) and output_language.strip():
        inner_payload["output_language"] = output_language.strip()

    action_body: dict[str, Any] = {
        "action_type": action_type,
        "title": title.strip(),
        "description": description.strip(),
        "priority": resolved_priority,
        "requires_approval": True,
        "payload": inner_payload,
    }

    if report_run_id is not None and str(report_run_id).strip():
        action_body["report_run_id"] = str(report_run_id).strip()

    return action_body


def map_content_suggestions_to_actions(
    suggestions: ContentSuggestions,
    *,
    report_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Map all validated drafts in a ContentSuggestions object to action request bodies."""
    resolved_report_run_id = report_run_id
    if resolved_report_run_id is None:
        resolved_report_run_id = suggestions.metadata.report_run_id

    return [
        map_content_draft_to_action_payload(
            draft,
            report_run_id=resolved_report_run_id,
        )
        for draft in suggestions.drafts
    ]


def persist_content_actions(
    suggestions: ContentSuggestions,
    *,
    django_client: DjangoClient,
    report_run_id: str | None = None,
    agent_output_id: str | None = None,
) -> list[dict[str, Any]]:
    """Persist mapped content actions through Django internal APIs only.

    Creates approval-required actions via ``POST /internal/ai/actions/``. Does not
    approve, execute, publish, or send anything.
    """
    action_bodies = map_content_suggestions_to_actions(
        suggestions,
        report_run_id=report_run_id,
    )
    persisted: list[dict[str, Any]] = []

    for action_body in action_bodies:
        request_body = dict(action_body)
        if agent_output_id is not None and "agent_output_id" not in request_body:
            request_body["agent_output_id"] = agent_output_id
        response = django_client.create_action(request_body)
        persisted.append(response)

    return persisted
