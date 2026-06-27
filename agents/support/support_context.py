"""Support message thread context extraction, normalization, and deterministic merge."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agents.shared.schemas.base import AgentWarning
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import (
    SupportMessageSenderRole,
    SupportMessageThreadContext,
    SupportSanitizedMessage,
    SupportSanitizedThread,
)
from agents.shared.schemas.validation import validate_agent_response

SUPPORT_AGENT_NAME = "support-agent"

_SENDER_ROLE_ALIASES: dict[str, str] = {
    "customer": "customer",
    "store": "store",
    "staff": "staff",
    "system": "system",
    "agent": "staff",
}


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def build_fetch_failure_warning(error_message: str) -> AgentWarning:
    return AgentWarning(
        code="django_fetch_failed",
        message=error_message,
    )


def build_message_thread_parse_warning(error_message: str) -> AgentWarning:
    return AgentWarning(
        code="message_thread_parse_warning",
        message=error_message,
    )


def _coerce_non_empty_string(value: Any) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_sender_role(value: Any) -> str | None:
    raw = _coerce_non_empty_string(value)
    if raw is None:
        return None
    return _SENDER_ROLE_ALIASES.get(raw.lower())


def normalize_sanitized_message(
    message: Mapping[str, Any],
    *,
    default_message_ref: str | None = None,
) -> SupportSanitizedMessage | None:
    """Normalize a sanitized message record from Django or caller context."""
    message_ref = (
        _coerce_non_empty_string(message.get("message_ref"))
        or _coerce_non_empty_string(message.get("message_id"))
        or _coerce_non_empty_string(message.get("id"))
        or default_message_ref
    )
    sender_role = _normalize_sender_role(
        message.get("sender_role") or message.get("sender_type")
    )
    text = _coerce_non_empty_string(message.get("text")) or _coerce_non_empty_string(
        message.get("body")
    )
    created_at = _coerce_non_empty_string(message.get("created_at")) or _coerce_non_empty_string(
        message.get("sent_at")
    )

    if message_ref is None or sender_role is None or text is None:
        return None

    return SupportSanitizedMessage(
        message_ref=message_ref,
        sender_role=cast(SupportMessageSenderRole, sender_role),
        text=text,
        created_at=created_at,
    )


def normalize_sanitized_thread(
    thread: Mapping[str, Any],
    *,
    default_thread_ref: str | None = None,
) -> tuple[SupportSanitizedThread | None, list[AgentWarning]]:
    """Normalize a sanitized thread record from Django or caller context."""
    warnings: list[AgentWarning] = []
    thread_ref = (
        _coerce_non_empty_string(thread.get("thread_ref"))
        or _coerce_non_empty_string(thread.get("thread_id"))
        or _coerce_non_empty_string(thread.get("id"))
        or default_thread_ref
    )
    if thread_ref is None:
        return None, [
            build_message_thread_parse_warning(
                "Skipped message thread entry with missing thread reference."
            )
        ]

    messages_raw = thread.get("messages")
    normalized_messages: list[SupportSanitizedMessage] = []
    if isinstance(messages_raw, list):
        for index, item in enumerate(messages_raw):
            if not isinstance(item, Mapping):
                warnings.append(
                    build_message_thread_parse_warning(
                        f"Skipped malformed message entry at index {index}."
                    )
                )
                continue
            normalized = normalize_sanitized_message(item)
            if normalized is None:
                warnings.append(
                    build_message_thread_parse_warning(
                        f"Skipped malformed message entry at index {index}."
                    )
                )
                continue
            normalized_messages.append(normalized)
    elif messages_raw is not None:
        warnings.append(
            build_message_thread_parse_warning(
                "Skipped malformed messages list on message thread entry."
            )
        )

    metadata = _coerce_mapping(thread.get("metadata"))
    if metadata is None:
        metadata = {}
    for key in ("customer_ref", "subject"):
        if key in thread and thread.get(key) is not None:
            metadata[key] = thread[key]
    if not metadata:
        metadata = None

    channel = _coerce_non_empty_string(thread.get("channel")) or _coerce_non_empty_string(
        thread.get("platform")
    )
    status = _coerce_non_empty_string(thread.get("status"))
    last_message_at = _coerce_non_empty_string(thread.get("last_message_at"))

    return (
        SupportSanitizedThread(
            thread_ref=thread_ref,
            messages=normalized_messages,
            channel=channel,
            status=status,
            last_message_at=last_message_at,
            metadata=metadata,
        ),
        warnings,
    )


def normalize_thread_list(
    threads: Any,
    *,
    source_label: str,
) -> tuple[list[SupportSanitizedThread], list[AgentWarning]]:
    warnings: list[AgentWarning] = []
    if threads is None:
        return [], warnings
    if not isinstance(threads, list):
        return [], [
            build_message_thread_parse_warning(
                f"Skipped malformed {source_label} message_threads payload."
            )
        ]

    normalized_threads: list[SupportSanitizedThread] = []
    for index, item in enumerate(threads):
        if not isinstance(item, Mapping):
            warnings.append(
                build_message_thread_parse_warning(
                    f"Skipped malformed {source_label} thread entry at index {index}."
                )
            )
            continue
        normalized, item_warnings = normalize_sanitized_thread(
            item,
            default_thread_ref=f"{source_label}-thread-{index + 1}",
        )
        warnings.extend(item_warnings)
        if normalized is not None:
            normalized_threads.append(normalized)

    return normalized_threads, warnings


def normalize_django_recent_messages_response(
    raw: Mapping[str, Any],
    *,
    store_id: str | None = None,
) -> tuple[dict[str, Any], list[AgentWarning]]:
    """Normalize Django recent-messages API payload into support context shape."""
    warnings: list[AgentWarning] = []
    threads, thread_warnings = normalize_thread_list(raw.get("threads"), source_label="django")
    warnings.extend(thread_warnings)

    resolved_store_id = _coerce_non_empty_string(raw.get("store_id")) or store_id
    thread_count = raw.get("thread_count")
    if not isinstance(thread_count, int) or isinstance(thread_count, bool):
        thread_count = len(threads)

    generated_at = _coerce_non_empty_string(raw.get("generated_at"))

    if "threads" not in raw:
        warnings.append(
            build_message_thread_parse_warning(
                "Django recent-messages payload missing threads list."
            )
        )

    normalized = {
        "store_id": resolved_store_id,
        "thread_count": thread_count,
        "message_threads": [thread.model_dump() for thread in threads],
        "django_fetched": True,
        "generated_at": generated_at,
    }
    return normalized, warnings


def _thread_sort_key(thread: SupportSanitizedThread) -> tuple[str, str]:
    last_message_at = thread.last_message_at or ""
    return (last_message_at, thread.thread_ref)


def merge_message_thread_lists(
    base: list[SupportSanitizedThread],
    overlay: list[SupportSanitizedThread],
) -> list[SupportSanitizedThread]:
    """Merge thread lists with overlay winning on duplicate ``thread_ref`` values."""
    index: dict[str, SupportSanitizedThread] = {
        thread.thread_ref: thread for thread in base
    }
    for thread in overlay:
        index[thread.thread_ref] = thread
    merged = list(index.values())
    merged.sort(key=_thread_sort_key, reverse=True)
    return merged


def merge_support_message_context(
    *,
    django_context: Mapping[str, Any] | None = None,
    caller_context: Mapping[str, Any] | None = None,
    message_threads: list[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[AgentWarning]]:
    """Merge Django-fetched and caller-supplied support message context deterministically.

    Merge rules:
    1. Django-fetched threads form the base when available.
    2. Caller ``context.message_threads`` overlays Django threads by ``thread_ref``.
    3. Explicit ``message_threads`` argument overlays both sources.
    4. Other caller ``context`` keys overlay top-level fields.
    """
    warnings: list[AgentWarning] = []
    merged: dict[str, Any] = {}

    django_threads: list[SupportSanitizedThread] = []
    if django_context is not None:
        merged.update(dict(django_context))
        django_threads, django_warnings = normalize_thread_list(
            django_context.get("message_threads"),
            source_label="django",
        )
        warnings.extend(django_warnings)

    caller = _coerce_mapping(caller_context)
    caller_threads: list[SupportSanitizedThread] = []
    if caller is not None:
        if "message_threads" in caller:
            caller_threads, caller_warnings = normalize_thread_list(
                caller.get("message_threads"),
                source_label="caller",
            )
            warnings.extend(caller_warnings)
        for key, value in caller.items():
            if key == "message_threads":
                continue
            merged[key] = value

    explicit_threads: list[SupportSanitizedThread] = []
    if message_threads is not None:
        explicit_threads, explicit_warnings = normalize_thread_list(
            message_threads,
            source_label="explicit",
        )
        warnings.extend(explicit_warnings)

    combined_threads = merge_message_thread_lists(django_threads, caller_threads)
    combined_threads = merge_message_thread_lists(combined_threads, explicit_threads)
    merged["message_threads"] = [thread.model_dump() for thread in combined_threads]
    merged["thread_count"] = len(combined_threads)

    if django_context is not None and django_context.get("django_fetched"):
        merged["django_fetched"] = True
    elif "django_fetched" not in merged:
        merged["django_fetched"] = False

    return merged, warnings


def resolve_support_message_context(
    *,
    context: Mapping[str, Any] | None = None,
    message_threads: list[Mapping[str, Any]] | None = None,
    django_context: Mapping[str, Any] | None = None,
) -> tuple[SupportMessageThreadContext, list[AgentWarning]]:
    """Resolve final sanitized support message-thread context and merge warnings."""
    merged, merge_warnings = merge_support_message_context(
        django_context=django_context,
        caller_context=context,
        message_threads=message_threads,
    )

    try:
        validated = validate_agent_response(merged, SupportMessageThreadContext)
    except AgentSchemaValidationError as exc:
        safe_context = SupportMessageThreadContext(
            store_id=_coerce_non_empty_string(merged.get("store_id")),
            thread_count=0,
            message_threads=[],
            django_fetched=bool(merged.get("django_fetched")),
            generated_at=_coerce_non_empty_string(merged.get("generated_at")),
        )
        warning = build_message_thread_parse_warning(
            f"Support message context validation failed: {exc}"
        )
        return safe_context, merge_warnings + [warning]

    return validated, merge_warnings
