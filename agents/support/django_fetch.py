"""Fetch sanitized support message threads from Django internal APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.shared.django_client import DjangoClient
from agents.shared.django_client.errors import DjangoClientError
from agents.shared.schemas.base import AgentWarning
from agents.support.support_context import (
    build_fetch_failure_warning,
    normalize_django_recent_messages_response,
)


def fetch_message_threads_from_django(
    django_client: DjangoClient,
    store_id: str,
    *,
    thread_limit: int | None = None,
    messages_per_thread: int | None = None,
) -> dict[str, Any]:
    """Fetch sanitized recent message threads for a store from Django."""
    raw = django_client.get_recent_messages(
        store_id,
        thread_limit=thread_limit,
        messages_per_thread=messages_per_thread,
    )
    normalized, _warnings = normalize_django_recent_messages_response(
        raw,
        store_id=store_id,
    )
    return normalized


def fetch_message_threads_with_fallback(
    *,
    django_client: DjangoClient | None,
    store_id: str | None,
    fetch_recent_messages: bool,
    thread_limit: int | None = None,
    messages_per_thread: int | None = None,
) -> tuple[dict[str, Any] | None, list[AgentWarning]]:
    """Fetch Django message threads or return ``None`` with a warning when fetch fails."""
    if not fetch_recent_messages:
        return None, []

    if django_client is None:
        return None, [
            build_fetch_failure_warning(
                "Django fetch requested but no Django client was configured."
            )
        ]

    if store_id is None or not str(store_id).strip():
        return None, [
            build_fetch_failure_warning(
                "Django fetch requested but store_id was not provided."
            )
        ]

    try:
        raw = django_client.get_recent_messages(
            str(store_id).strip(),
            thread_limit=thread_limit,
            messages_per_thread=messages_per_thread,
        )
        normalized, parse_warnings = normalize_django_recent_messages_response(
            raw,
            store_id=str(store_id).strip(),
        )
        return normalized, parse_warnings
    except DjangoClientError:
        return None, [
            build_fetch_failure_warning("Message thread fetch from Django failed.")
        ]
