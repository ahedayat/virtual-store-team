"""Unit tests for Content Agent action mapping and persistence (Step 8.6)."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch

import httpx

from agents.content.action_mapping import (
    ContentActionMappingError,
    DEFAULT_CONTENT_ACTION_PRIORITY,
    map_content_draft_to_action_payload,
    map_content_suggestions_to_actions,
    persist_content_actions,
)
from agents.content.tests.test_schema_validation import (
    build_instagram_draft,
    build_product_description_draft,
    build_valid_content_payload,
)
from agents.content.validation import ensure_valid_content_suggestions
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.content import ContentDraft


class ContentActionMappingTests(unittest.TestCase):
    def test_instagram_draft_maps_to_content_instagram_draft(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft())

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["action_type"], "content.instagram_draft")
        self.assertEqual(action_body["title"], draft.title)
        self.assertEqual(action_body["description"], draft.description)

    def test_product_description_maps_to_content_product_description(self) -> None:
        draft = ContentDraft.model_validate(build_product_description_draft())

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["action_type"], "content.product_description")

    def test_mapped_actions_include_requires_approval_true(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft())

        action_body = map_content_draft_to_action_payload(draft)

        self.assertTrue(action_body["requires_approval"])

    def test_unsupported_content_action_type_is_rejected(self) -> None:
        draft = build_instagram_draft(action_type="content.publish_instagram")

        with self.assertRaises(ContentActionMappingError) as context:
            map_content_draft_to_action_payload(draft)

        self.assertIn("Unsupported content action_type", str(context.exception))

    def test_product_reference_is_preserved_when_available(self) -> None:
        draft = ContentDraft.model_validate(build_product_description_draft())

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(
            action_body["payload"]["product_id"],
            "00000000-0000-4000-8000-000000000002",
        )

    def test_draft_text_is_preserved_in_payload(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft())

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["payload"]["draft_text"], draft.draft_text)
        self.assertEqual(action_body["payload"]["rationale"], draft.rationale)

    def test_priority_defaults_when_missing(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft(priority=None))

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["priority"], DEFAULT_CONTENT_ACTION_PRIORITY)

    def test_priority_is_preserved_when_provided(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft(priority=2))

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["priority"], 2)

    def test_report_run_id_is_included_when_provided(self) -> None:
        draft = ContentDraft.model_validate(build_instagram_draft())

        action_body = map_content_draft_to_action_payload(
            draft,
            report_run_id="run-map-1",
        )

        self.assertEqual(action_body["report_run_id"], "run-map-1")

    def test_extra_draft_payload_fields_are_merged(self) -> None:
        draft = ContentDraft.model_validate(
            build_instagram_draft(
                payload={"channel": "instagram", "format": "caption"},
            )
        )

        action_body = map_content_draft_to_action_payload(draft)

        self.assertEqual(action_body["payload"]["channel"], "instagram")
        self.assertEqual(action_body["payload"]["format"], "caption")
        self.assertEqual(action_body["payload"]["draft_text"], draft.draft_text)

    def test_map_content_suggestions_to_actions_uses_metadata_report_run_id(self) -> None:
        suggestions = ensure_valid_content_suggestions(
            build_valid_content_payload(
                drafts=[
                    build_instagram_draft(),
                    build_product_description_draft(),
                ],
            )
        )

        action_bodies = map_content_suggestions_to_actions(suggestions)

        self.assertEqual(len(action_bodies), 2)
        for body in action_bodies:
            self.assertEqual(body["report_run_id"], "run-valid-1")
            self.assertTrue(body["requires_approval"])


class ContentActionPersistenceTests(unittest.TestCase):
    def test_persist_content_actions_posts_to_internal_actions_endpoint(self) -> None:
        suggestions = ensure_valid_content_suggestions(build_valid_content_payload())
        captured_bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertEqual(
                str(request.url),
                "http://backend:8000/internal/ai/actions/",
            )
            captured_bodies.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                201,
                json={
                    "id": f"action-{len(captured_bodies)}",
                    "status": "pending_approval",
                    "requires_approval": True,
                    "action_type": captured_bodies[-1]["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            service_token="test-token",
            request_id="req-1",
            max_retries=0,
            http_client=http_client,
        )

        with patch.object(client, "create_action", wraps=client.create_action) as mocked_create:
            results = persist_content_actions(
                suggestions,
                django_client=client,
                report_run_id="run-persist-1",
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "pending_approval")
        mocked_create.assert_called_once()

        posted = captured_bodies[0]
        self.assertEqual(posted["action_type"], "content.instagram_draft")
        self.assertTrue(posted["requires_approval"])
        self.assertEqual(posted["report_run_id"], "run-persist-1")
        self.assertIn("draft_text", posted["payload"])

    def test_persist_content_actions_forwards_agent_output_id(self) -> None:
        suggestions = ensure_valid_content_suggestions(build_valid_content_payload())
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                201,
                json={
                    "id": "action-1",
                    "status": "pending_approval",
                    "requires_approval": True,
                    "action_type": captured_body["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        persist_content_actions(
            suggestions,
            django_client=client,
            agent_output_id="output-uuid-1",
        )

        self.assertEqual(captured_body["agent_output_id"], "output-uuid-1")

    def test_persist_content_actions_does_not_execute_or_publish(self) -> None:
        suggestions = ensure_valid_content_suggestions(build_valid_content_payload())

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            self.assertNotIn("execute", request.url.path)
            self.assertNotIn("publish", request.url.path)
            self.assertTrue(body["requires_approval"])
            return httpx.Response(
                201,
                json={
                    "id": "action-1",
                    "status": "pending_approval",
                    "requires_approval": True,
                    "action_type": body["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        results = persist_content_actions(suggestions, django_client=client)

        self.assertEqual(results[0]["status"], "pending_approval")


class DjangoClientCreateActionTests(unittest.TestCase):
    def test_create_action_posts_json_to_internal_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(201, json={"id": "action-1", "status": "pending_approval"})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        response = client.create_action(
            {
                "action_type": "content.instagram_draft",
                "title": "Caption",
                "description": "Draft",
                "priority": 3,
                "requires_approval": True,
                "payload": {"draft_text": "Hello"},
            }
        )

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/internal/ai/actions/")
        self.assertEqual(captured["body"]["action_type"], "content.instagram_draft")
        self.assertEqual(response["status"], "pending_approval")


if __name__ == "__main__":
    unittest.main()
