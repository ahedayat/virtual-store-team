"""Unit tests for Support Agent Django message-thread fetching (Step 9.5)."""

from __future__ import annotations

import unittest
from typing import Any

import httpx

from agents.shared.django_client import DjangoClient
from agents.support.django_fetch import (
    fetch_message_threads_from_django,
    fetch_message_threads_with_fallback,
)


def build_django_recent_messages_response() -> dict[str, Any]:
    return {
        "generated_at": "2026-06-27T12:00:00+00:00",
        "store_id": "00000000-0000-4000-8000-000000000020",
        "thread_count": 1,
        "threads": [
            {
                "thread_id": "00000000-0000-4000-8000-000000000021",
                "customer_ref": "customer-00000000-0000-4000-8000-000000000099",
                "platform": "instagram",
                "status": "open",
                "subject": "Product availability question",
                "last_message_at": "2026-06-27T11:30:00+00:00",
                "messages": [
                    {
                        "message_id": "00000000-0000-4000-8000-000000000031",
                        "direction": "inbound",
                        "sender_type": "customer",
                        "body": "Hi, is the demo tote still available? Contact: [PHONE_REDACTED]",
                        "sent_at": "2026-06-27T11:00:00+00:00",
                    },
                    {
                        "message_id": "00000000-0000-4000-8000-000000000032",
                        "direction": "outbound",
                        "sender_type": "staff",
                        "body": "Thanks for reaching out. The demo tote is still available.",
                        "sent_at": "2026-06-27T11:30:00+00:00",
                    },
                ],
            }
        ],
    }


class SupportDjangoFetchTests(unittest.TestCase):
    def _build_client(self, handler) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            service_token="test-token",
            request_id="trace-support-fetch-1",
            max_retries=0,
            http_client=http_client,
        )

    def test_successful_django_fetch_returns_normalized_threads(self) -> None:
        store_id = "00000000-0000-4000-8000-000000000020"

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                request.url.path,
                f"/internal/ai/stores/{store_id}/messages/recent/",
            )
            self.assertEqual(request.headers.get("Authorization"), "Bearer test-token")
            self.assertEqual(request.headers.get("X-Request-ID"), "trace-support-fetch-1")
            return httpx.Response(200, json=build_django_recent_messages_response())

        client = self._build_client(handler)
        context = fetch_message_threads_from_django(client, store_id)

        self.assertTrue(context["django_fetched"])
        self.assertEqual(context["thread_count"], 1)
        self.assertEqual(len(context["message_threads"]), 1)
        thread = context["message_threads"][0]
        self.assertEqual(thread["thread_ref"], "00000000-0000-4000-8000-000000000021")
        self.assertEqual(thread["channel"], "instagram")
        self.assertEqual(len(thread["messages"]), 2)
        self.assertEqual(thread["messages"][0]["sender_role"], "customer")
        self.assertIn("[PHONE_REDACTED]", thread["messages"][0]["text"])
        self.assertNotIn("@", thread["messages"][0]["text"])

    def test_django_client_failure_returns_safe_warning(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "Service unavailable."})

        client = self._build_client(handler)
        django_context, warnings = fetch_message_threads_with_fallback(
            django_client=client,
            store_id="00000000-0000-4000-8000-000000000020",
            fetch_recent_messages=True,
        )

        self.assertIsNone(django_context)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].code, "django_fetch_failed")
        self.assertNotIn("Service unavailable", warnings[0].message)

    def test_fetch_disabled_returns_no_django_context(self) -> None:
        django_context, warnings = fetch_message_threads_with_fallback(
            django_client=None,
            store_id="00000000-0000-4000-8000-000000000020",
            fetch_recent_messages=False,
        )

        self.assertIsNone(django_context)
        self.assertEqual(warnings, [])

    def test_missing_store_id_returns_safe_warning(self) -> None:
        django_context, warnings = fetch_message_threads_with_fallback(
            django_client=self._build_client(
                lambda request: httpx.Response(200, json=build_django_recent_messages_response())
            ),
            store_id=None,
            fetch_recent_messages=True,
        )

        self.assertIsNone(django_context)
        self.assertEqual(warnings[0].code, "django_fetch_failed")


class DjangoClientRecentMessagesEndpointTests(unittest.TestCase):
    def test_get_recent_messages_uses_expected_path(self) -> None:
        captured_paths: list[str] = []
        store_id = "00000000-0000-4000-8000-000000000020"

        def handler(request: httpx.Request) -> httpx.Response:
            captured_paths.append(request.url.path)
            return httpx.Response(200, json=build_django_recent_messages_response())

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        client.get_recent_messages(store_id)

        self.assertEqual(
            captured_paths,
            [f"/internal/ai/stores/{store_id}/messages/recent/"],
        )


if __name__ == "__main__":
    unittest.main()
