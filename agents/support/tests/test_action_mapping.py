"""Unit tests for Support Agent action mapping and persistence (Step 9.7)."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from agents.shared.django_client import DjangoClient
from agents.shared.schemas.support import SupportInsights, SupportReplyDraft
from agents.support.action_mapping import (
    SupportActionMappingError,
    map_support_insights_to_actions,
    map_support_reply_draft_to_action_payload,
    persist_support_actions,
)
from agents.support.app.main import app
from agents.support.tests.test_support_insights_schema import (
    build_reply_draft,
    build_valid_support_insights_payload,
)
from agents.support.validation import ensure_valid_support_insights

_SYNTHETIC_EMAIL = "[EMAIL_REDACTED]"
_SYNTHETIC_PHONE = "[PHONE_REDACTED]"


class SupportActionMappingTests(unittest.TestCase):
    def test_valid_reply_draft_maps_to_django_compatible_payload(self) -> None:
        draft = SupportReplyDraft.model_validate(build_reply_draft())
        action_body = map_support_reply_draft_to_action_payload(draft)

        self.assertEqual(action_body["action_type"], "support.reply_draft")
        self.assertFalse(action_body["requires_approval"])
        self.assertEqual(action_body["payload"]["thread_ref"], "thread-ref-001")
        self.assertEqual(action_body["payload"]["policy_code"], "generic_faq")
        self.assertEqual(action_body["payload"]["source"], "support-agent")
        self.assertTrue(action_body["payload"]["low_risk"])
        self.assertIn("draft", action_body["title"].lower())

    def test_valid_escalate_maps_to_django_compatible_payload(self) -> None:
        draft = SupportReplyDraft.model_validate(
            build_reply_draft(
                action_type="support.escalate",
                requires_approval=True,
                risk_level="high",
                matched_policy_code="angry_or_escalated_customer",
                reply_text="A manager will review this conversation shortly.",
                reason="Customer tone requires manager review.",
                safety_notes=["Manager approval is required before escalation."],
            )
        )
        action_body = map_support_reply_draft_to_action_payload(draft)

        self.assertEqual(action_body["action_type"], "support.escalate")
        self.assertTrue(action_body["requires_approval"])
        self.assertEqual(
            action_body["payload"]["reason"],
            "Customer tone requires manager review.",
        )
        self.assertNotIn("reply_text", action_body["payload"])

    def test_unsupported_action_type_is_rejected(self) -> None:
        draft = build_reply_draft(action_type="support.send_message")

        with self.assertRaises(SupportActionMappingError) as context:
            map_support_reply_draft_to_action_payload(draft)

        self.assertIn("Unsupported support action_type", str(context.exception))

    def test_missing_required_draft_fields_are_rejected(self) -> None:
        with self.assertRaises(SupportActionMappingError) as context:
            map_support_reply_draft_to_action_payload(
                build_reply_draft(thread_ref="   ")
            )

        self.assertIn("thread_ref is required", str(context.exception))

        with self.assertRaises(SupportActionMappingError) as context:
            map_support_reply_draft_to_action_payload(
                build_reply_draft(reply_text="   ")
            )

        self.assertIn("reply_text is required", str(context.exception))

        with self.assertRaises(SupportActionMappingError) as context:
            map_support_reply_draft_to_action_payload(
                build_reply_draft(
                    action_type="support.escalate",
                    requires_approval=True,
                    risk_level="high",
                    reason=None,
                    rationale=None,
                )
            )

        self.assertIn("reason is required", str(context.exception))

    def test_sensitive_draft_remains_approval_required(self) -> None:
        draft = SupportReplyDraft.model_validate(
            build_reply_draft(
                requires_approval=True,
                risk_level="high",
                matched_policy_code="refund_request",
                reply_text="We will review your refund request with a manager.",
            )
        )
        action_body = map_support_reply_draft_to_action_payload(draft)

        self.assertTrue(action_body["requires_approval"])
        self.assertNotIn("low_risk", action_body["payload"])

    def test_low_risk_draft_maps_low_risk_only_when_policy_allows(self) -> None:
        low_risk_draft = SupportReplyDraft.model_validate(build_reply_draft())
        low_risk_body = map_support_reply_draft_to_action_payload(low_risk_draft)
        self.assertFalse(low_risk_body["requires_approval"])
        self.assertTrue(low_risk_body["payload"]["low_risk"])

        medium_risk_draft = SupportReplyDraft.model_validate(
            build_reply_draft(
                requires_approval=True,
                risk_level="medium",
                matched_policy_code="order_status_question",
            )
        )
        medium_risk_body = map_support_reply_draft_to_action_payload(medium_risk_draft)
        self.assertTrue(medium_risk_body["requires_approval"])
        self.assertNotIn("low_risk", medium_risk_body["payload"])

    def test_map_support_insights_uses_metadata_report_run_id(self) -> None:
        insights = ensure_valid_support_insights(
            build_valid_support_insights_payload(
                reply_drafts=[
                    build_reply_draft(),
                    build_reply_draft(
                        thread_ref="thread-ref-002",
                        requires_approval=True,
                        risk_level="high",
                        matched_policy_code="refund_request",
                    ),
                ]
            )
        )

        action_bodies = map_support_insights_to_actions(insights)

        self.assertEqual(len(action_bodies), 2)
        for body in action_bodies:
            self.assertEqual(body["report_run_id"], "run-support-1")

    def test_mapped_payloads_do_not_contain_raw_pii(self) -> None:
        draft = SupportReplyDraft.model_validate(
            build_reply_draft(
                reply_text=(
                    "Thank you for contacting us. We received your question about store hours."
                ),
                rationale="Generic FAQ draft without customer identifiers.",
            )
        )
        action_body = map_support_reply_draft_to_action_payload(draft)
        serialized = json.dumps(action_body)

        self.assertNotIn(_SYNTHETIC_EMAIL, serialized)
        self.assertNotIn(_SYNTHETIC_PHONE, serialized)
        self.assertNotIn("sent", action_body["title"].lower())
        self.assertNotIn("refund issued", serialized.lower())
        self.assertNotIn("order changed", serialized.lower())

    def test_mapped_payloads_do_not_claim_external_side_effects(self) -> None:
        draft = SupportReplyDraft.model_validate(build_reply_draft())
        action_body = map_support_reply_draft_to_action_payload(draft)

        combined = f"{action_body['title']} {action_body['description']}".lower()
        self.assertNotIn("message sent", combined)
        self.assertNotIn("refund issued", combined)
        self.assertNotIn("order updated", combined)


class SupportActionPersistenceTests(unittest.TestCase):
    def test_dry_run_maps_without_posting(self) -> None:
        insights = ensure_valid_support_insights(build_valid_support_insights_payload())

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("Django POST must not occur in dry_run mode")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        mapped = persist_support_actions(
            insights,
            django_client=client,
            dry_run=True,
        )

        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]["action_type"], "support.reply_draft")

    def test_successful_action_persistence_posts_to_internal_actions(self) -> None:
        insights = ensure_valid_support_insights(build_valid_support_insights_payload())
        captured_bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_bodies.append(json.loads(request.content.decode("utf-8")))
            self.assertEqual(request.url.path, "/internal/ai/actions/")
            return httpx.Response(
                201,
                json={
                    "id": "action-support-1",
                    "status": "queued",
                    "requires_approval": False,
                    "action_type": captured_bodies[-1]["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        responses = persist_support_actions(
            insights,
            django_client=client,
            report_run_id="run-persist-support-1",
        )

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["status"], "queued")
        self.assertEqual(captured_bodies[0]["action_type"], "support.reply_draft")
        self.assertEqual(captured_bodies[0]["report_run_id"], "run-persist-support-1")

    def test_persistence_failure_preserves_support_insights(self) -> None:
        from agents.shared.django_client.errors import DjangoHTTPError
        from agents.shared.schemas.base import AgentWarning
        from agents.support.app.main import _append_warning

        insights = ensure_valid_support_insights(build_valid_support_insights_payload())
        original_summary = insights.summary

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "Invalid action payload."})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        preserved = insights
        try:
            persist_support_actions(
                preserved,
                django_client=client,
            )
        except DjangoHTTPError:
            preserved = _append_warning(
                preserved,
                AgentWarning(
                    code="support_action_persistence_failed",
                    message="Support action persistence failed.",
                ),
            )

        self.assertIsInstance(preserved, SupportInsights)
        self.assertEqual(preserved.summary, original_summary)
        self.assertGreaterEqual(len(preserved.reply_drafts), 1)
        self.assertTrue(
            any(item.code == "support_action_persistence_failed" for item in preserved.warnings)
        )
        self.assertNotIn("Invalid action payload", json.dumps(preserved.model_dump()))

    @patch.dict("os.environ", {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_dry_run_does_not_persist(self) -> None:
        client = TestClient(app)

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("Django POST must not occur when dry_run is true")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        django_client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        with patch("agents.support.app.main._build_django_client", return_value=django_client):
            response = client.post(
                "/run",
                json={
                    "customer_message": "What are your store hours?",
                    "channel": "instagram_dm",
                    "persist_actions": True,
                    "dry_run": True,
                    "service_token": "test-token",
                    "output_language": "en",
                },
            )

        self.assertEqual(response.status_code, 200)
        warnings = response.json()["warnings"]
        self.assertTrue(any(item["code"] == "dry_run" for item in warnings))

    @patch.dict("os.environ", {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_persistence_failure_returns_safe_warning(self) -> None:
        client = TestClient(app)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "Invalid action payload."})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        django_client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        with patch("agents.support.app.main._build_django_client", return_value=django_client):
            response = client.post(
                "/run",
                json={
                    "customer_message": "What are your store hours?",
                    "channel": "instagram_dm",
                    "persist_actions": True,
                    "service_token": "test-token",
                    "output_language": "en",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("reply", body)
        warnings = body["warnings"]
        self.assertTrue(
            any(item["code"] == "support_action_persistence_failed" for item in warnings)
        )
        self.assertNotIn("Invalid action payload", json.dumps(body))


if __name__ == "__main__":
    unittest.main()
