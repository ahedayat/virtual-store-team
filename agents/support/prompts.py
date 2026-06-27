"""Support Agent prompt templates for scaffold mock replies (Phase 6.6)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents.shared.language import build_language_prompt_prefix


def _role_and_scope_section() -> str:
    return "\n".join(
        [
            "You are the Support Agent for a multi-tenant virtual store management platform.",
            "Your role is limited to customer support message understanding, safe reply drafts, and support escalation.",
            "Produce reviewable reply drafts for store managers; do not send messages or execute actions.",
            "Do not perform sales analysis, content generation, pricing decisions, inventory actions, refunds,",
            "order mutation, payment handling, or manager approval bypass.",
            "Out-of-scope requests must return structured refusal output instead of attempting the task.",
            "Stay tenant-agnostic: use only sanitized message context supplied in the request.",
        ]
    )


def _safety_and_guardrails_section() -> str:
    return "\n".join(
        [
            "Safety and scope guardrails:",
            "- Do not send Instagram DMs, emails, or any external customer contact.",
            "- Do not process refunds, change orders, adjust prices, or update inventory.",
            "- Do not access databases, internal APIs, credentials, or secrets.",
            "- Do not impersonate specialist sales, marketing/content, or coordinator workflows.",
            "- Do not bypass manager approval for sensitive or side-effectful operations.",
            "- Do not include phone numbers, emails, addresses, or payment details in outputs.",
            "- Do not claim that an external side effect has been performed.",
            "- Escalation, when needed, must use support.escalate and require manager approval.",
        ]
    )


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

    system_content = "\n\n".join(
        [
            _role_and_scope_section(),
            build_language_prompt_prefix(output_language),
            _safety_and_guardrails_section(),
            "Return a structured support reply envelope with intent and review flags.",
        ]
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(user_payload, default=str)},
    ]
