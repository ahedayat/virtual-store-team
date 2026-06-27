"""Merge specialist outputs into the final daily report payload (Step 10.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.shared.schemas.base import AgentWarning


def _serialize_warnings(warnings: list[AgentWarning]) -> list[dict[str, str]]:
    return [{"code": warning.code, "message": warning.message} for warning in warnings]


def _missing_sections(
    *,
    sales_output: dict[str, Any] | None,
    content_output: dict[str, Any] | None,
    support_output: dict[str, Any] | None,
) -> list[str]:
    missing: list[str] = []
    if sales_output is None:
        missing.append("sales")
    if content_output is None:
        missing.append("content")
    if support_output is None:
        missing.append("support")
    return missing


def _extract_sales_summary(
    *,
    context: dict[str, Any] | None,
    sales_output: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(context, dict):
        summary = context.get("sales_summary")
        if isinstance(summary, dict) and summary:
            return dict(summary)

    if isinstance(sales_output, dict):
        summary_text = sales_output.get("summary")
        if isinstance(summary_text, str) and summary_text.strip():
            return {"summary": summary_text.strip()}

    return {}


def _dedupe_key(recommendation: dict[str, Any]) -> str | None:
    payload = recommendation.get("payload")
    if isinstance(payload, dict):
        for key in ("sku", "product_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    title = recommendation.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def build_prioritized_actions(sales_output: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(sales_output, dict):
        return []

    recommendations = sales_output.get("recommendations")
    if not isinstance(recommendations, list):
        return []

    prioritized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for recommendation in sorted(
        (item for item in recommendations if isinstance(item, dict)),
        key=lambda item: item.get("priority", 99),
    ):
        dedupe_key = _dedupe_key(recommendation)
        if dedupe_key is not None:
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

        action_type = recommendation.get("action_type")
        title = recommendation.get("title")
        description = recommendation.get("description")
        summary = title if isinstance(title, str) and title.strip() else description
        if not isinstance(summary, str) or not summary.strip():
            continue

        entry: dict[str, Any] = {
            "priority": recommendation.get("priority"),
            "summary": summary.strip(),
        }
        if isinstance(action_type, str) and action_type.strip():
            entry["action_type"] = action_type.strip()
        prioritized.append(entry)

    return prioritized


def build_content_suggestions(content_output: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(content_output, dict):
        return []

    drafts = content_output.get("drafts")
    if not isinstance(drafts, list):
        return []

    suggestions: list[dict[str, Any]] = []
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        action_type = draft.get("action_type")
        draft_text = draft.get("draft_text")
        title = draft.get("title")
        preview_source = draft_text if isinstance(draft_text, str) else title
        if not isinstance(preview_source, str) or not preview_source.strip():
            continue

        preview = preview_source.strip()
        if len(preview) > 160:
            preview = f"{preview[:157]}..."

        entry: dict[str, Any] = {"draft_preview": preview}
        if isinstance(action_type, str) and action_type.strip():
            entry["type"] = action_type.strip()
        suggestions.append(entry)

    return suggestions


def build_support_insights(support_output: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(support_output, dict):
        return []

    themes = support_output.get("themes")
    if isinstance(themes, list) and themes:
        summary = support_output.get("summary")
        sentiment = support_output.get("sentiment")
        sentiment_label = sentiment.get("label") if isinstance(sentiment, dict) else None
        insights: list[dict[str, Any]] = []
        for theme in themes:
            if not isinstance(theme, str) or not theme.strip():
                continue
            entry: dict[str, Any] = {
                "theme": theme.strip(),
                "summary": summary.strip()
                if isinstance(summary, str) and summary.strip()
                else f"Support theme: {theme.strip()}",
            }
            if isinstance(sentiment_label, str) and sentiment_label.strip():
                entry["sentiment"] = sentiment_label.strip()
            insights.append(entry)
        if insights:
            return insights

    intent = support_output.get("intent")
    status = support_output.get("status")
    requires_review = support_output.get("requires_human_review")
    theme = intent if isinstance(intent, str) and intent.strip() else "support_inquiry"
    entry = {
        "theme": theme,
        "summary": "Support specialist completed analysis for recent customer threads.",
    }
    if isinstance(status, str) and status.strip():
        entry["status"] = status.strip()
    if isinstance(requires_review, bool):
        entry["requires_human_review"] = requires_review
    return [entry]


def build_next_steps(
    *,
    prioritized_actions: list[dict[str, Any]],
    content_suggestions: list[dict[str, Any]],
    support_insights: list[dict[str, Any]],
    partial: bool,
) -> list[str]:
    steps: list[str] = []
    if prioritized_actions:
        steps.append("Review prioritized sales actions; approval is required before execution.")
    if content_suggestions:
        steps.append("Review generated content drafts before any external publishing.")
    if support_insights:
        steps.append("Review support reply drafts and escalations before customer contact.")
    if partial:
        steps.append("Review workflow warnings for specialist sections that did not complete.")
    if not steps:
        steps.append("Review the daily report with the management team.")
    return steps


def build_merged_daily_report(
    *,
    report_run_id: str,
    store_id: str,
    context: dict[str, Any] | None,
    sales_output: dict[str, Any] | None,
    content_output: dict[str, Any] | None,
    support_output: dict[str, Any] | None,
    agent_outputs_ref: list[str],
    workflow_warnings: list[AgentWarning],
) -> dict[str, Any]:
    """Build the coordinator daily report document submitted to Django."""
    missing_sections = _missing_sections(
        sales_output=sales_output,
        content_output=content_output,
        support_output=support_output,
    )
    partial = bool(missing_sections)

    sales_summary = _extract_sales_summary(context=context, sales_output=sales_output)
    prioritized_actions = build_prioritized_actions(sales_output)
    content_suggestions = build_content_suggestions(content_output)
    support_insights = build_support_insights(support_output)
    report_warnings = _serialize_warnings(workflow_warnings)

    generated_at = None
    if isinstance(context, dict):
        raw_generated_at = context.get("generated_at")
        if isinstance(raw_generated_at, str) and raw_generated_at.strip():
            generated_at = raw_generated_at.strip()
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    period = None
    if isinstance(context, dict) and isinstance(context.get("period"), dict):
        period = dict(context["period"])

    return {
        "report_run_id": report_run_id,
        "store_id": store_id,
        "generated_at": generated_at,
        "period": period,
        "sales_summary": sales_summary,
        "prioritized_actions": prioritized_actions,
        "content_suggestions": content_suggestions,
        "support_insights": support_insights,
        "next_steps": build_next_steps(
            prioritized_actions=prioritized_actions,
            content_suggestions=content_suggestions,
            support_insights=support_insights,
            partial=partial,
        ),
        "agent_outputs_ref": list(agent_outputs_ref),
        "warnings": report_warnings,
        "sections": {
            key: {"present": True}
            for key, output in (
                ("sales", sales_output),
                ("content", content_output),
                ("support", support_output),
            )
            if output is not None
        },
        "missing_sections": missing_sections,
        "partial": partial,
    }
