"""Support Agent prompt templates for scaffold mock replies (Phase 6.6)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents.shared.language import build_language_prompt_prefix


def build_support_reply_messages(
    *,
    customer_message: str,
    channel: str,
    tenant_id: str | None = None,
    store_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    output_language: str | None = None,
    request_id: str | None = None,
) -> list[dict[str, str]]:
    """Build scaffold prompt messages for the Support Agent mock pipeline."""
    user_payload: dict[str, Any] = {
        "customer_message": customer_message,
        "channel": channel,
    }
    if tenant_id is not None:
        user_payload["tenant_id"] = tenant_id
    if store_id is not None:
        user_payload["store_id"] = store_id
    if metadata is not None:
        user_payload["metadata"] = dict(metadata)
    if request_id is not None:
        user_payload["request_id"] = request_id

    system_content = "\n".join(
        [
            "You are the Support Agent for a multi-tenant virtual store management platform.",
            "Your role is limited to safe customer support reply drafting and intent classification.",
            "Do not execute actions, change orders, or access raw PII beyond sanitized message text.",
            build_language_prompt_prefix(output_language),
            "Return a structured support reply envelope with intent and review flags.",
        ]
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(user_payload, default=str)},
    ]
