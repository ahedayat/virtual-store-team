"""Unit tests for Support Agent message-thread context merge (Step 9.5)."""

from __future__ import annotations

import unittest
from typing import Any

from agents.support.django_fetch import fetch_message_threads_with_fallback
from agents.support.support_context import (
    merge_support_message_context,
    resolve_support_message_context,
)


def build_caller_thread() -> dict[str, Any]:
    return {
        "thread_ref": "thread-caller-1",
        "channel": "instagram",
        "status": "open",
        "last_message_at": "2026-06-27T10:00:00+00:00",
        "messages": [
            {
                "message_ref": "msg-caller-1",
                "sender_role": "customer",
                "text": "Caller-provided sanitized thread message.",
                "created_at": "2026-06-27T09:55:00+00:00",
            }
        ],
    }


def build_django_context() -> dict[str, Any]:
    return {
        "store_id": "00000000-0000-4000-8000-000000000020",
        "thread_count": 2,
        "django_fetched": True,
        "generated_at": "2026-06-27T12:00:00+00:00",
        "message_threads": [
            {
                "thread_ref": "thread-django-1",
                "channel": "instagram",
                "status": "open",
                "last_message_at": "2026-06-27T11:30:00+00:00",
                "messages": [
                    {
                        "message_ref": "msg-django-1",
                        "sender_role": "customer",
                        "text": "Django fetched sanitized message.",
                        "created_at": "2026-06-27T11:00:00+00:00",
                    }
                ],
            },
            {
                "thread_ref": "thread-shared",
                "channel": "instagram",
                "status": "open",
                "last_message_at": "2026-06-27T10:30:00+00:00",
                "messages": [
                    {
                        "message_ref": "msg-django-shared",
                        "sender_role": "customer",
                        "text": "Django version of shared thread.",
                        "created_at": "2026-06-27T10:00:00+00:00",
                    }
                ],
            },
        ],
    }


class SupportMessageThreadContextTests(unittest.TestCase):
    def test_caller_threads_preserved_when_fetch_disabled(self) -> None:
        merged, warnings = merge_support_message_context(
            message_threads=[build_caller_thread()],
        )

        self.assertEqual(warnings, [])
        self.assertFalse(merged["django_fetched"])
        self.assertEqual(len(merged["message_threads"]), 1)
        self.assertEqual(merged["message_threads"][0]["thread_ref"], "thread-caller-1")

    def test_caller_and_django_context_merge_deterministically(self) -> None:
        caller_context = {
            "message_threads": [build_caller_thread()],
            "store": {"display_name": "Demo Store"},
        }

        merged, warnings = merge_support_message_context(
            django_context=build_django_context(),
            caller_context=caller_context,
        )

        self.assertEqual(warnings, [])
        thread_refs = [thread["thread_ref"] for thread in merged["message_threads"]]
        self.assertEqual(
            thread_refs,
            ["thread-django-1", "thread-shared", "thread-caller-1"],
        )
        self.assertEqual(merged["store"]["display_name"], "Demo Store")
        self.assertTrue(merged["django_fetched"])

    def test_duplicate_thread_refs_use_overlay_precedence(self) -> None:
        overlay_thread = {
            "thread_ref": "thread-shared",
            "channel": "instagram",
            "status": "pending",
            "last_message_at": "2026-06-27T12:00:00+00:00",
            "messages": [
                {
                    "message_ref": "msg-caller-shared",
                    "sender_role": "staff",
                    "text": "Caller overlay wins for duplicate thread_ref.",
                    "created_at": "2026-06-27T12:00:00+00:00",
                }
            ],
        }

        merged, warnings = merge_support_message_context(
            django_context=build_django_context(),
            message_threads=[overlay_thread],
        )

        self.assertEqual(warnings, [])
        shared = next(
            thread
            for thread in merged["message_threads"]
            if thread["thread_ref"] == "thread-shared"
        )
        self.assertEqual(shared["status"], "pending")
        self.assertEqual(shared["messages"][0]["message_ref"], "msg-caller-shared")

    def test_fetch_failure_continues_with_caller_context(self) -> None:
        django_context, fetch_warnings = fetch_message_threads_with_fallback(
            django_client=None,
            store_id="00000000-0000-4000-8000-000000000020",
            fetch_recent_messages=True,
        )
        resolved, merge_warnings = resolve_support_message_context(
            context={"message_threads": [build_caller_thread()]},
            django_context=django_context,
        )

        self.assertEqual(len(fetch_warnings), 1)
        self.assertEqual(fetch_warnings[0].code, "django_fetch_failed")
        self.assertEqual(merge_warnings, [])
        self.assertEqual(resolved.thread_count, 1)
        self.assertEqual(resolved.message_threads[0].thread_ref, "thread-caller-1")

    def test_malformed_optional_django_payload_returns_safe_warnings(self) -> None:
        merged, warnings = merge_support_message_context(
            django_context={
                "django_fetched": True,
                "message_threads": "not-a-list",
            }
        )

        self.assertEqual(merged["message_threads"], [])
        self.assertEqual(warnings[0].code, "message_thread_parse_warning")

    def test_resolved_context_contains_no_raw_pii_placeholders(self) -> None:
        resolved, _warnings = resolve_support_message_context(
            message_threads=[
                {
                    "thread_ref": "thread-safe-1",
                    "messages": [
                        {
                            "message_ref": "msg-safe-1",
                            "sender_role": "customer",
                            "text": "Please email customer_123@redacted.local or call [PHONE_REDACTED].",
                            "created_at": "2026-06-27T09:00:00+00:00",
                        }
                    ],
                }
            ]
        )

        serialized = resolved.model_dump_json()
        self.assertIn("[PHONE_REDACTED]", serialized)
        self.assertIn("redacted.local", serialized)
        self.assertNotRegex(serialized, r"\+?\d{10,}")


if __name__ == "__main__":
    unittest.main()
