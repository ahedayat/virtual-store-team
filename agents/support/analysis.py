"""Support Agent runtime analysis pipeline (Phase 9.6)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from agents.shared.django_client import DjangoClient
from agents.shared.language import get_output_language, normalize_output_language
from agents.shared.llm import get_llm_provider
from agents.shared.schemas.base import AgentWarning
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import (
    SupportAggregateSentiment,
    SupportInsights,
    SupportMessageThreadContext,
    SupportReplyDraft,
    SupportSanitizedMessage,
    SupportSanitizedThread,
    SupportScopeEvaluation,
)
from agents.support.approval_policy import evaluate_support_approval_policy
from agents.support.django_fetch import fetch_message_threads_with_fallback
from agents.support.injection_guard import sanitize_support_reply_output
from agents.support.prompts import build_support_analysis_messages
from agents.support.refusal import (
    detect_in_scope_support_category,
    evaluate_support_scope,
)
from agents.support.support_context import resolve_support_message_context
from agents.support.validation import (
    SupportLLMOutputError,
    ensure_valid_support_insights,
    log_support_validation_failure,
    parse_llm_json_output,
)

SUPPORT_AGENT_NAME = "support-agent"
REFUSAL_WARNING_CODE = "support_out_of_scope_refusal"
EMPTY_THREADS_WARNING_CODE = "no_support_threads_available"

_NEGATIVE_SENTIMENT_CATEGORIES = frozenset(
    {
        "angry_or_escalated_customer",
        "legal_or_safety_claim",
        "refund_request",
        "cancellation_request",
        "payment_issue",
        "order_dispute",
    }
)
_POSITIVE_SENTIMENT_CATEGORIES = frozenset({"generic_faq", "product_question"})


class LLMProvider(Protocol):
    """Minimal protocol for Support Agent LLM integration."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


def _resolve_output_language(output_language: str | None) -> str:
    if output_language is None:
        return get_output_language()
    return normalize_output_language(output_language)


def _attach_warnings(
    result: SupportInsights,
    warnings: list[AgentWarning],
) -> SupportInsights:
    if not warnings:
        return result
    combined = list(result.warnings) + warnings
    return result.model_copy(update={"warnings": combined})


def _customer_messages(thread: SupportSanitizedThread) -> list[SupportSanitizedMessage]:
    return [message for message in thread.messages if message.sender_role == "customer"]


def _latest_customer_message(thread: SupportSanitizedThread) -> SupportSanitizedMessage | None:
    customer_messages = _customer_messages(thread)
    if not customer_messages:
        return None
    return max(
        customer_messages,
        key=lambda message: message.created_at or "",
    )


def _thread_has_customer_text(thread: SupportSanitizedThread) -> bool:
    return _latest_customer_message(thread) is not None


def _threads_with_customer_text(
    threads: list[SupportSanitizedThread],
) -> list[SupportSanitizedThread]:
    return [thread for thread in threads if _thread_has_customer_text(thread)]


def _synthesize_thread_from_customer_message(
    *,
    customer_message: str,
    channel: str,
    thread_ref: str,
) -> SupportSanitizedThread:
    return SupportSanitizedThread(
        thread_ref=thread_ref,
        channel=channel,
        messages=[
            SupportSanitizedMessage(
                message_ref=f"{thread_ref}-msg-1",
                sender_role="customer",
                text=customer_message,
            )
        ],
    )


def _resolve_thread_context(
    *,
    context: Mapping[str, Any] | None,
    message_threads: list[Mapping[str, Any]] | None,
    customer_message: str | None,
    channel: str,
    request_id: str | None,
    django_client: DjangoClient | None,
    fetch_recent_messages: bool,
    store_id: str | None,
) -> tuple[SupportMessageThreadContext, list[AgentWarning]]:
    django_context, fetch_warnings = fetch_message_threads_with_fallback(
        django_client=django_client,
        store_id=store_id,
        fetch_recent_messages=fetch_recent_messages,
    )
    resolved_context, merge_warnings = resolve_support_message_context(
        context=context,
        message_threads=message_threads,
        django_context=django_context,
    )
    pipeline_warnings = fetch_warnings + merge_warnings

    if resolved_context.message_threads:
        return resolved_context, pipeline_warnings

    explicit_thread_input = (
        message_threads is not None
        or (context is not None and "message_threads" in context)
        or fetch_recent_messages
    )
    if explicit_thread_input:
        return resolved_context, pipeline_warnings

    if customer_message and customer_message.strip():
        thread_ref = request_id.strip() if request_id and request_id.strip() else "thread-single-1"
        synthesized = _synthesize_thread_from_customer_message(
            customer_message=customer_message.strip(),
            channel=channel,
            thread_ref=thread_ref,
        )
        return (
            resolved_context.model_copy(
                update={
                    "message_threads": [synthesized],
                    "thread_count": 1,
                }
            ),
            pipeline_warnings,
        )

    return resolved_context, pipeline_warnings


def _collect_thread_categories(threads: list[SupportSanitizedThread]) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for thread in threads:
        message = _latest_customer_message(thread)
        if message is None:
            continue
        category = detect_in_scope_support_category(message.text)
        if category not in seen:
            seen.add(category)
            categories.append(category)
    return categories


def _summarize_support_sentiment(categories: list[str]) -> SupportAggregateSentiment:
    if not categories:
        return SupportAggregateSentiment(label="unknown", confidence=0.5)

    negative = sum(1 for category in categories if category in _NEGATIVE_SENTIMENT_CATEGORIES)
    positive = sum(1 for category in categories if category in _POSITIVE_SENTIMENT_CATEGORIES)

    if negative > 0 and positive > 0:
        return SupportAggregateSentiment(label="mixed", confidence=0.75)
    if negative > 0:
        confidence = 0.88 if negative == len(categories) else 0.8
        return SupportAggregateSentiment(label="negative", confidence=confidence)
    if positive > 0 and positive == len(categories):
        return SupportAggregateSentiment(label="positive", confidence=0.85)
    return SupportAggregateSentiment(label="neutral", confidence=0.82)


def _build_summary_text(
    *,
    categories: list[str],
    thread_count: int,
    output_language: str,
) -> str:
    if not categories:
        if output_language == "en":
            return "No customer support messages were available for analysis."
        return "هیچ پیام پشتیبانی مشتری برای تحلیل در دسترس نبود."

    primary_theme = categories[0]
    if output_language == "en":
        if thread_count > 1:
            return (
                f"Analyzed {thread_count} sanitized support threads. "
                f"Primary theme: {primary_theme.replace('_', ' ')}."
            )
        return (
            f"Analyzed one sanitized support thread with theme: {primary_theme.replace('_', ' ')}."
        )

    if thread_count > 1:
        return (
            f"{thread_count} رشته پیام پشتیبانی پاک‌سازی‌شده تحلیل شد. "
            f"موضوع اصلی: {primary_theme}."
        )
    return f"یک رشته پیام پشتیبانی پاک‌سازی‌شده با موضوع {primary_theme} تحلیل شد."


def _build_refusal_insights(
    *,
    scope: SupportScopeEvaluation,
    thread_ref: str,
    output_language: str,
    report_run_id: str | None,
    request_id: str | None,
) -> SupportInsights:
    resolved_report_run_id = report_run_id or request_id
    refusal_policy_code = scope.refusal_code or "unsupported_external_action"
    draft = SupportReplyDraft(
        thread_ref=thread_ref,
        reply_text=scope.safe_message,
        action_type="support.escalate",
        requires_approval=True,
        risk_level="high",
        matched_policy_code=refusal_policy_code,
        safety_notes=["Out-of-scope request refused; no external action executed."],
        rationale=scope.reason,
        language=output_language,
    )
    return SupportInsights(
        metadata={
            "agent_name": SUPPORT_AGENT_NAME,
            "report_run_id": resolved_report_run_id,
        },
        summary=scope.safe_message,
        themes=[refusal_policy_code],
        sentiment=SupportAggregateSentiment(label="neutral", confidence=1.0),
        reply_drafts=[draft],
        warnings=[
            AgentWarning(
                code=REFUSAL_WARNING_CODE,
                message=scope.reason,
            )
        ],
        output_language=output_language,
    )


def _build_empty_thread_insights(
    *,
    output_language: str,
    report_run_id: str | None,
    request_id: str | None,
) -> SupportInsights:
    resolved_report_run_id = report_run_id or request_id
    if output_language == "en":
        summary = "No customer support messages were available for analysis."
        reply_text = (
            "No recent customer messages are available. "
            "A manager can review this support run when new messages arrive."
        )
    else:
        summary = "هیچ پیام پشتیبانی مشتری برای تحلیل در دسترس نبود."
        reply_text = (
            "پیام اخیر مشتری در دسترس نیست. "
            "مدیر می‌تواند پس از دریافت پیام‌های جدید این اجرای پشتیبانی را بررسی کند."
        )

    draft = SupportReplyDraft(
        thread_ref="thread-empty",
        reply_text=reply_text,
        action_type="support.escalate",
        requires_approval=True,
        risk_level="medium",
        matched_policy_code="unknown_or_ambiguous",
        safety_notes=["No customer messages available; draft is informational only."],
        rationale="Empty support thread context requires manager review before contact.",
        language=output_language,
    )
    return SupportInsights(
        metadata={
            "agent_name": SUPPORT_AGENT_NAME,
            "report_run_id": resolved_report_run_id,
        },
        summary=summary,
        themes=[],
        sentiment=SupportAggregateSentiment(label="unknown", confidence=0.5),
        reply_drafts=[draft],
        warnings=[
            AgentWarning(
                code=EMPTY_THREADS_WARNING_CODE,
                message="No sanitized support threads with customer messages were available.",
            )
        ],
        output_language=output_language,
    )


def _apply_policy_to_draft(
    *,
    draft_data: Mapping[str, Any],
    category: str,
    source_message: str,
) -> SupportReplyDraft:
    policy = evaluate_support_approval_policy(category)
    reply_text = str(draft_data.get("reply_text", "")).strip()
    sanitized_reply = sanitize_support_reply_output(reply_text, source_message)

    action_type = draft_data.get("action_type", policy.default_action_type)
    if action_type not in {"support.reply_draft", "support.escalate"}:
        action_type = policy.default_action_type

    requires_approval = bool(draft_data.get("requires_approval", policy.requires_approval))
    if policy.requires_approval:
        requires_approval = True
    if action_type == "support.escalate":
        requires_approval = True

    risk_level = draft_data.get("risk_level", policy.risk_level)
    matched_policy_code = draft_data.get("matched_policy_code", policy.matched_policy_code)

    safety_notes_raw = draft_data.get("safety_notes")
    safety_notes = (
        [str(item) for item in safety_notes_raw]
        if isinstance(safety_notes_raw, list)
        else []
    )
    if policy.requires_approval and not safety_notes:
        safety_notes = ["Manager approval is required before any external customer contact."]

    return SupportReplyDraft(
        thread_ref=str(draft_data.get("thread_ref", "thread-unknown")),
        reply_text=sanitized_reply,
        action_type=action_type,
        requires_approval=requires_approval,
        risk_level=risk_level,
        matched_policy_code=str(matched_policy_code),
        safety_notes=safety_notes,
        reason=draft_data.get("reason"),
        rationale=draft_data.get("rationale", policy.reason),
        language=draft_data.get("language"),
    )


def _normalize_llm_insights(
    parsed: Mapping[str, Any],
    *,
    threads: list[SupportSanitizedThread],
    output_language: str,
    report_run_id: str | None,
) -> dict[str, Any]:
    payload = dict(parsed)
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    metadata_payload = dict(metadata)
    metadata_payload.setdefault("agent_name", SUPPORT_AGENT_NAME)
    if report_run_id and not metadata_payload.get("report_run_id"):
        metadata_payload["report_run_id"] = report_run_id
    payload["metadata"] = metadata_payload
    payload.setdefault("output_language", output_language)

    categories = _collect_thread_categories(threads)
    payload.setdefault("themes", categories)
    if "sentiment" not in payload:
        payload["sentiment"] = _summarize_support_sentiment(categories).model_dump()

    drafts_raw = payload.get("reply_drafts")
    normalized_drafts: list[dict[str, Any]] = []
    if isinstance(drafts_raw, list):
        for index, item in enumerate(drafts_raw):
            if not isinstance(item, Mapping):
                continue
            thread = threads[index] if index < len(threads) else threads[0]
            source_message = _latest_customer_message(thread)
            source_text = source_message.text if source_message is not None else ""
            category = detect_in_scope_support_category(source_text)
            draft = _apply_policy_to_draft(
                draft_data=item,
                category=category,
                source_message=source_text,
            )
            normalized_drafts.append(draft.model_dump())

    if not normalized_drafts:
        for thread in threads:
            source_message = _latest_customer_message(thread)
            if source_message is None:
                continue
            category = detect_in_scope_support_category(source_message.text)
            policy = evaluate_support_approval_policy(category)
            if output_language == "en":
                reply_text = (
                    "Thank you for your message. "
                    "We prepared a reviewable support reply draft for manager review."
                )
            else:
                reply_text = (
                    "از پیام شما سپاسگزاریم. "
                    "یک پیش‌نویس پاسخ پشتیبانی قابل بررسی برای مدیر آماده شد."
                )
            draft = _apply_policy_to_draft(
                draft_data={
                    "thread_ref": thread.thread_ref,
                    "reply_text": reply_text,
                    "action_type": policy.default_action_type,
                    "requires_approval": policy.requires_approval,
                    "risk_level": policy.risk_level,
                    "matched_policy_code": policy.matched_policy_code,
                    "safety_notes": (
                        ["Manager approval is required before any external customer contact."]
                        if policy.requires_approval
                        else []
                    ),
                    "rationale": policy.reason,
                    "language": output_language,
                },
                category=category,
                source_message=source_message.text,
            )
            normalized_drafts.append(draft.model_dump())

    payload["reply_drafts"] = normalized_drafts
    if "summary" not in payload or not str(payload.get("summary", "")).strip():
        payload["summary"] = _build_summary_text(
            categories=categories,
            thread_count=len(threads),
            output_language=output_language,
        )
    return payload


def _run_llm_support_analysis(
    *,
    thread_context: SupportMessageThreadContext,
    channel: str,
    tenant_id: str | None,
    store_id: str | None,
    metadata: Mapping[str, Any] | None,
    threads: list[SupportSanitizedThread],
    output_language: str,
    report_run_id: str | None,
    request_id: str | None,
    llm_provider: LLMProvider,
) -> SupportInsights:
    messages = build_support_analysis_messages(
        thread_context=thread_context,
        channel=channel,
        tenant_id=tenant_id,
        store_id=store_id,
        metadata=metadata,
        output_language=output_language,
        request_id=request_id,
    )

    try:
        raw_output = llm_provider.complete(messages)
        parsed = parse_llm_json_output(raw_output)
        normalized = _normalize_llm_insights(
            parsed,
            threads=threads,
            output_language=output_language,
            report_run_id=report_run_id,
        )
        return ensure_valid_support_insights(normalized)
    except (AgentSchemaValidationError, SupportLLMOutputError) as exc:
        log_support_validation_failure(exc, request_id=request_id)
        raise


def run_support_analysis(
    *,
    customer_message: str,
    channel: str,
    tenant_id: str | None = None,
    store_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    request_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    context: Mapping[str, Any] | None = None,
    message_threads: list[Mapping[str, Any]] | None = None,
    django_client: DjangoClient | None = None,
    fetch_recent_messages: bool = False,
) -> SupportInsights:
    """Run the Support Agent runtime pipeline and return schema-valid SupportInsights."""
    language = _resolve_output_language(output_language)

    thread_context, pipeline_warnings = _resolve_thread_context(
        context=context,
        message_threads=message_threads,
        customer_message=customer_message,
        channel=channel,
        request_id=request_id,
        django_client=django_client,
        fetch_recent_messages=fetch_recent_messages,
        store_id=store_id,
    )

    active_threads = _threads_with_customer_text(thread_context.message_threads)
    if not active_threads:
        empty_result = _build_empty_thread_insights(
            output_language=language,
            report_run_id=report_run_id,
            request_id=request_id,
        )
        return _attach_warnings(empty_result, pipeline_warnings)

    primary_text = ""
    primary_thread_ref = active_threads[0].thread_ref
    refusal_scope: SupportScopeEvaluation | None = None

    for thread in active_threads:
        message = _latest_customer_message(thread)
        if message is None:
            continue
        scope = evaluate_support_scope(message.text, output_language=language)
        if scope.is_refusal:
            refusal_scope = scope
            primary_thread_ref = thread.thread_ref
            primary_text = message.text
            break
        if not primary_text:
            primary_text = message.text
            primary_thread_ref = thread.thread_ref

    if refusal_scope is not None:
        refusal_result = _build_refusal_insights(
            scope=refusal_scope,
            thread_ref=primary_thread_ref,
            output_language=language,
            report_run_id=report_run_id,
            request_id=request_id,
        )
        return _attach_warnings(refusal_result, pipeline_warnings)

    if not primary_text:
        empty_result = _build_empty_thread_insights(
            output_language=language,
            report_run_id=report_run_id,
            request_id=request_id,
        )
        return _attach_warnings(empty_result, pipeline_warnings)

    provider = llm_provider if llm_provider is not None else get_llm_provider()
    result = _run_llm_support_analysis(
        thread_context=thread_context.model_copy(update={"message_threads": active_threads}),
        channel=channel,
        tenant_id=tenant_id,
        store_id=store_id,
        metadata=metadata,
        threads=active_threads,
        output_language=language,
        report_run_id=report_run_id,
        request_id=request_id,
        llm_provider=provider,
    )

    updates: dict[str, Any] = {}
    if report_run_id and result.metadata.report_run_id is None:
        updates["metadata"] = result.metadata.model_copy(
            update={"report_run_id": report_run_id}
        )
    if result.output_language != language:
        updates["output_language"] = language

    if updates:
        result = result.model_copy(update=updates)

    return _attach_warnings(result, pipeline_warnings)
