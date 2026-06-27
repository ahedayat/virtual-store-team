"""Full coordinator graph integration tests with mock LLM across services (Phase 10.4)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from agents.coordinator.config import CoordinatorNodeTimeouts
from agents.coordinator.nodes import WorkflowNodeDependencies
from agents.coordinator.runner import run_daily_report_workflow
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.tests.integration_harness import (
    CONTENT_HOST,
    DJANGO_HOST,
    INTEGRATION_CONTEXT_BUNDLE,
    SALES_HOST,
    SUPPORT_HOST,
    VALID_REPORT_RUN_ID,
    VALID_STORE_ID,
    VALID_TENANT_ID,
    RecordingDjangoState,
    ServiceRouterTransport,
    build_integration_django_client,
    build_integration_http_client,
    build_integration_specialist_client,
)
from agents.coordinator.topology import (
    SPECIALIST_PEER_CALL_PATHS,
    assert_star_topology,
)


def _workflow_state(**overrides: object) -> DailyReportWorkflowState:
    defaults: dict[str, Any] = {
        "report_run_id": VALID_REPORT_RUN_ID,
        "tenant_id": VALID_TENANT_ID,
        "store_id": VALID_STORE_ID,
        "service_token": "service-jwt",
        "request_id": "integration-req-1",
    }
    defaults.update(overrides)
    return DailyReportWorkflowState(**defaults)


def _build_deps(
    transport: ServiceRouterTransport,
    *,
    node_timeouts: CoordinatorNodeTimeouts | None = None,
) -> WorkflowNodeDependencies:
    http_client = build_integration_http_client(transport)
    django_client = build_integration_django_client(http_client)

    def specialist_factory(timeout_seconds: float):
        return build_integration_specialist_client(
            http_client,
            timeout_seconds=timeout_seconds,
        )

    return WorkflowNodeDependencies(
        django_client=django_client,
        specialist_client_factory=specialist_factory,
        node_timeouts=node_timeouts,
    )


@patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
class FullGraphIntegrationSuccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.django_state = RecordingDjangoState()
        self.transport = ServiceRouterTransport(django_state=self.django_state)
        self.deps = _build_deps(self.transport)

    def test_full_graph_calls_django_context_sales_content_support_and_complete(self) -> None:
        result = run_daily_report_workflow(_workflow_state(), self.deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(self.django_state.context_calls), 1)
        self.assertEqual(len(self.django_state.agent_output_calls), 3)
        self.assertEqual(len(self.django_state.complete_calls), 1)
        self.assertEqual(self.django_state.action_calls, [])

        hosts_called = {entry["host"] for entry in self.transport.request_log}
        self.assertIn(SALES_HOST, hosts_called)
        self.assertIn(CONTENT_HOST, hosts_called)
        self.assertIn(SUPPORT_HOST, hosts_called)
        self.assertIn(DJANGO_HOST, hosts_called)

        specialist_run_calls = [
            entry
            for entry in self.transport.request_log
            if entry["method"] == "POST" and entry["path"] == "/run"
        ]
        self.assertEqual(len(specialist_run_calls), 3)

    def test_specialist_payloads_disable_persistence_and_django_fetch(self) -> None:
        run_daily_report_workflow(_workflow_state(), self.deps)

        self.assertEqual(len(self.transport.specialist_run_bodies), 3)
        sales_body = self.transport.specialist_run_bodies[0]
        self.assertFalse(sales_body.get("fetch_from_django", True))
        self.assertFalse(sales_body.get("persist_actions", True))
        self.assertTrue(sales_body.get("dry_run", False))

        support_body = next(
            body for body in self.transport.specialist_run_bodies if body.get("customer_message")
        )
        self.assertEqual(support_body["channel"], "instagram_dm")
        self.assertFalse(support_body.get("fetch_recent_messages", True))
        self.assertFalse(support_body.get("persist_actions", True))
        self.assertTrue(support_body.get("dry_run", False))

    def test_final_report_contains_required_sections_and_agent_output_refs(self) -> None:
        result = run_daily_report_workflow(_workflow_state(), self.deps)

        report = result.merged_report
        self.assertIsNotNone(report)
        assert report is not None

        self.assertIn("sales_summary", report)
        self.assertTrue(report["sales_summary"])
        self.assertIn("prioritized_actions", report)
        self.assertIn("content_suggestions", report)
        self.assertIn("support_insights", report)
        self.assertIn("next_steps", report)
        self.assertEqual(report["agent_outputs_ref"], result.agent_outputs_ref)
        self.assertEqual(len(report["agent_outputs_ref"]), 3)
        self.assertIn("generated_at", report)
        self.assertFalse(report["partial"])

        complete_body = self.django_state.complete_calls[0]
        self.assertEqual(complete_body["agent_output_ids"], result.agent_outputs_ref)
        self.assertEqual(
            complete_body["report"]["agent_outputs_ref"],
            result.agent_outputs_ref,
        )

    def test_specialist_outputs_are_schema_compatible(self) -> None:
        result = run_daily_report_workflow(_workflow_state(), self.deps)

        self.assertIsNotNone(result.sales_output)
        self.assertIsNotNone(result.content_output)
        self.assertIsNotNone(result.support_output)

        sales = result.sales_output
        assert sales is not None
        self.assertEqual(sales["metadata"]["agent_name"], "sales-agent")
        self.assertIsInstance(sales.get("recommendations"), list)

        content = result.content_output
        assert content is not None
        self.assertEqual(content["metadata"]["agent_name"], "content-agent")
        self.assertIsInstance(content.get("drafts"), list)

        support = result.support_output
        assert support is not None
        self.assertEqual(support.get("agent"), "support-agent")
        self.assertIn(support.get("status"), {"ok", "refused"})

    def test_coordinator_does_not_auto_approve_or_execute_actions(self) -> None:
        result = run_daily_report_workflow(_workflow_state(), self.deps)

        self.assertEqual(self.django_state.action_calls, [])
        action_paths = [
            entry["path"]
            for entry in self.transport.request_log
            if "/actions/" in entry["path"]
        ]
        self.assertEqual(action_paths, [])

        report = result.merged_report
        assert report is not None
        for action in report.get("prioritized_actions", []):
            self.assertNotIn("status", action)
            self.assertNotIn("approved", action)

    def test_star_topology_only_coordinator_calls_specialists(self) -> None:
        assert_star_topology()
        self.assertEqual(SPECIALIST_PEER_CALL_PATHS, frozenset())

        run_daily_report_workflow(_workflow_state(), self.deps)

        specialist_hosts = {SALES_HOST, CONTENT_HOST, SUPPORT_HOST}
        coordinator_to_specialist = [
            entry
            for entry in self.transport.request_log
            if entry["host"] in specialist_hosts and entry["path"] == "/run"
        ]
        self.assertEqual(len(coordinator_to_specialist), 3)

        peer_calls = [
            entry
            for entry in self.transport.request_log
            if entry["host"] in specialist_hosts
            and entry["path"] != "/run"
        ]
        self.assertEqual(peer_calls, [])

    def test_context_bundle_is_used_for_sales_summary_in_final_report(self) -> None:
        result = run_daily_report_workflow(_workflow_state(), self.deps)

        report = result.merged_report
        assert report is not None
        self.assertEqual(
            report["sales_summary"]["today"]["order_count"],
            INTEGRATION_CONTEXT_BUNDLE["sales_summary"]["today"]["order_count"],
        )


@patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
class FullGraphIntegrationPartialFailureTests(unittest.TestCase):
    def test_support_timeout_produces_partial_report_with_warnings(self) -> None:
        django_state = RecordingDjangoState()
        transport = ServiceRouterTransport(
            django_state=django_state,
            support_delay_seconds=0.25,
        )
        deps = _build_deps(
            transport,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=5.0,
                sales_seconds=5.0,
                content_seconds=5.0,
                support_seconds=0.05,
                merge_seconds=5.0,
                submit_seconds=5.0,
            ),
        )

        result = run_daily_report_workflow(_workflow_state(), deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertIsNone(result.support_output)
        self.assertIsNotNone(result.sales_output)
        self.assertIsNotNone(result.content_output)

        report = result.merged_report
        assert report is not None
        self.assertTrue(report["partial"])
        self.assertIn("support", report["missing_sections"])
        self.assertIn("warnings", report)
        self.assertTrue(any(item["code"] == "specialist_node_timeout" for item in report["warnings"]))

        warning_blob = json.dumps(report["warnings"])
        self.assertNotIn("Bearer", warning_blob)
        self.assertNotIn("service-jwt", warning_blob)
        self.assertNotIn("customer@", warning_blob.lower())

        self.assertEqual(len(django_state.agent_output_calls), 2)
        self.assertEqual(len(django_state.complete_calls), 1)
        self.assertIsNotNone(result.sales_output)
        self.assertIsNotNone(result.content_output)
        self.assertIn("sales", report["sections"])
        self.assertIn("content", report["sections"])
        self.assertNotIn("support", report["sections"])


@patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
class MergeUnitTests(unittest.TestCase):
    def test_merge_prioritizes_and_dedupes_sales_recommendations(self) -> None:
        from agents.coordinator.merge import build_merged_daily_report

        report = build_merged_daily_report(
            report_run_id=VALID_REPORT_RUN_ID,
            store_id=VALID_STORE_ID,
            context=INTEGRATION_CONTEXT_BUNDLE,
            sales_output={
                "summary": "Sales ok",
                "recommendations": [
                    {
                        "priority": 2,
                        "action_type": "sales.restock",
                        "title": "Restock SKU-1",
                        "description": "Low stock",
                        "rationale": "Velocity",
                        "payload": {"sku": "SKU-1"},
                    },
                    {
                        "priority": 1,
                        "action_type": "sales.discount",
                        "title": "Discount SKU-1 duplicate",
                        "description": "Duplicate",
                        "rationale": "Dup",
                        "payload": {"sku": "SKU-1"},
                    },
                ],
            },
            content_output={"drafts": [{"action_type": "content.instagram_draft", "draft_text": "Hello", "title": "t", "description": "d", "rationale": "r", "requires_approval": True}]},
            support_output={"agent": "support-agent", "status": "ok", "intent": "generic_faq", "requires_human_review": False},
            agent_outputs_ref=["out-1"],
            workflow_warnings=[],
        )

        self.assertEqual(report["prioritized_actions"][0]["priority"], 1)
        self.assertEqual(len(report["prioritized_actions"]), 1)


if __name__ == "__main__":
    unittest.main()
