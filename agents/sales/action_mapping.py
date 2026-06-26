"""Map validated Sales Agent recommendations to Django-compatible action payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.sales.prompts import ALLOWED_SALES_ACTION_TYPES
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.sales import SalesAnalysisResult, SalesRecommendation

SUPPORTED_SALES_ACTION_TYPES = frozenset(ALLOWED_SALES_ACTION_TYPES)

_REQUIRED_PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    "sales.restock": ("sku",),
    "sales.discount": ("sku",),
    "sales.follow_up": ("follow_up_reason",),
}


class SalesActionMappingError(ValueError):
    """Raised when a sales recommendation cannot be mapped to a supported action payload."""


def _coerce_non_empty_string(value: Any) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def map_sales_recommendation_to_action_payload(
    recommendation: SalesRecommendation | Mapping[str, Any],
    *,
    report_run_id: str | None = None,
) -> dict[str, Any]:
    """Convert a validated sales recommendation into a Django internal action request body."""
    if isinstance(recommendation, SalesRecommendation):
        action_type = recommendation.action_type
        title = recommendation.title
        description = recommendation.description
        rationale = recommendation.rationale
        priority = recommendation.priority
        recommendation_payload = dict(recommendation.payload)
    else:
        action_type = recommendation.get("action_type")
        title = recommendation.get("title")
        description = recommendation.get("description")
        rationale = recommendation.get("rationale")
        priority = recommendation.get("priority")
        raw_payload = recommendation.get("payload", {})
        recommendation_payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}

    if action_type not in SUPPORTED_SALES_ACTION_TYPES:
        raise SalesActionMappingError(
            f"Unsupported sales action_type: {action_type!r}. "
            f"Allowed types: {sorted(SUPPORTED_SALES_ACTION_TYPES)}."
        )

    if not _coerce_non_empty_string(title):
        raise SalesActionMappingError("title is required for sales action mapping.")
    if not _coerce_non_empty_string(description):
        raise SalesActionMappingError("description is required for sales action mapping.")
    if not _coerce_non_empty_string(rationale):
        raise SalesActionMappingError("rationale is required for sales action mapping.")
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise SalesActionMappingError("priority must be an integer for sales action mapping.")
    if priority < 1 or priority > 5:
        raise SalesActionMappingError("priority must be between 1 and 5 for sales action mapping.")

    required_fields = _REQUIRED_PAYLOAD_FIELDS.get(action_type, ())
    inner_payload: dict[str, Any] = dict(recommendation_payload)
    inner_payload["rationale"] = rationale.strip()

    for field_name in required_fields:
        if field_name == "follow_up_reason":
            value = (
                _coerce_non_empty_string(inner_payload.get("follow_up_reason"))
                or _coerce_non_empty_string(inner_payload.get("reason"))
            )
            if value is None:
                raise SalesActionMappingError(
                    "follow_up_reason is required for sales.follow_up action mapping."
                )
            inner_payload["follow_up_reason"] = value
            continue

        value = _coerce_non_empty_string(inner_payload.get(field_name))
        if value is None:
            raise SalesActionMappingError(
                f"{field_name} is required for {action_type} action mapping."
            )
        inner_payload[field_name] = value

    action_body: dict[str, Any] = {
        "action_type": action_type,
        "title": title.strip(),
        "description": description.strip(),
        "priority": priority,
        "requires_approval": True,
        "payload": inner_payload,
    }

    if report_run_id is not None and str(report_run_id).strip():
        action_body["report_run_id"] = str(report_run_id).strip()

    return action_body


def map_sales_analysis_to_actions(
    result: SalesAnalysisResult,
    *,
    report_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Map all validated recommendations in a SalesAnalysisResult to action request bodies."""
    resolved_report_run_id = report_run_id
    if resolved_report_run_id is None:
        resolved_report_run_id = result.metadata.report_run_id

    return [
        map_sales_recommendation_to_action_payload(
            recommendation,
            report_run_id=resolved_report_run_id,
        )
        for recommendation in result.recommendations
    ]


def persist_sales_actions(
    result: SalesAnalysisResult,
    *,
    django_client: DjangoClient,
    report_run_id: str | None = None,
    agent_output_id: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Persist mapped sales actions through Django internal APIs only.

    When ``dry_run`` is True, actions are mapped and returned without POSTing to Django.
    """
    action_bodies = map_sales_analysis_to_actions(
        result,
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
