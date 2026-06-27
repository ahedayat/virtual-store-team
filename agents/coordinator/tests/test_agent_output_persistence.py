"""Tests for coordinator AgentOutput persistence (Phase 10.3)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from agents.coordinator.agent_output_persistence import (
    build_agent_output_request,
    persist_specialist_agent_output,
    sanitize_specialist_output_payload,
)
from agents.coordinator.nodes import (
    WorkflowNodeDependencies,
    node_merge,
    node_run_content,
    node_run_sales,
    node_run_support,
    node_submit,
)
from agents.coordinator.runner import run_daily_report_workflow
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.workflow import (
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
)
from agents.shared.django_client import DjangoHTTPError

VALID_REPORT_RUN_ID = "11111111-1111-4111-8111-111111111111"
VALID_TENANT_ID = "22222222-2222-4222-8222-222222222222"
VALID_STORE_ID = "33333333-3333-4333-8333-333333333333"


def _base_state(**overrides: object) -> DailyReportWorkflowState:
    defaults: dict[str, Any] = {
        "report_run_id": VALID_REPORT_RUN_ID,
        "tenant_id": VALID_TENANT_ID,
        "store_id": VALID_STORE_ID,
        "service_token": "service-jwt",
        "request_id": "req-persistence-test",
    }
    defaults.update(overrides)
    return DailyReportWorkflowState(**defaults)


def _specialist_response(agent_name: str, *, summary: str = "section ok") -> dict[str, Any]:
    return {
        "summary": summary,
        "metadata": {"agent_name": agent_name},
        "tenant_id": "untrusted-tenant",
        "store_id": "untrusted-store",
    }


class _RecordingDjangoClient:
    def __init__(
        self,
        *,
        fail_nodes: frozenset[str] = frozenset(),
        timeout_seconds: float | None = None,
    ) -> None:
        self.fail_nodes = fail_nodes
        self.timeout_seconds = timeout_seconds
        self.agent_output_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self._counter = 0

    def get_context_bundle(self, report_run_id: str) -> dict[str, Any]:
        return {"report_run_id": report_run_id, "store": {}}

    def create_agent_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.agent_output_calls.append(payload)
        node_name = payload.get("metadata", {}).get("coordinator_node")
        if node_name in self.fail_nodes:
            raise DjangoHTTPError(500, "Persistence failed.")
        self._counter += 1
        return {
            "id": f"aaaaaaaa-aaaa-4aaa-8aaa-{self._counter:012d}",
            "agent_name": "coordinator-agent",
            "output_type": payload.get("output_type"),
            "report_run_id": payload.get("report_run_id"),
        }

    def complete_report_run(
        self,
        report_run_id: str,
        *,
        report: dict[str, Any],
        agent_output_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self.submit_calls.append(
            {
                "report_run_id": report_run_id,
                "report": report,
                "agent_output_ids": agent_output_ids,
            }
        )
        return {"status": "completed", "report_run_id": report_run_id}


class _MockSpecialistClient:
    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    def run_sales(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("sales")
        return self.responses.get(
            "sales",
            _specialist_response("sales-agent", summary="sales ok"),
        )

    def run_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("content")
        return self.responses.get(
            "content",
            _specialist_response("content-agent", summary="content ok"),
        )

    def run_support(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("support")
        return self.responses.get(
            "support",
            _specialist_response("support-agent", summary="support ok"),
        )


class AgentOutputSanitizationTests(unittest.TestCase):
    def test_sanitize_removes_untrusted_scope_fields(self) -> None:
        sanitized = sanitize_specialist_output_payload(
            {
                "summary": "ok",
                "tenant_id": "bad-tenant",
                "store_id": "bad-store",
                "metadata": {
                    "agent_name": "sales-agent",
                    "tenant_id": "bad-tenant",
                    "store_id": "bad-store",
                },
            }
        )

        self.assertNotIn("tenant_id", sanitized)
        self.assertNotIn("store_id", sanitized)
        self.assertNotIn("tenant_id", sanitized["metadata"])
        self.assertNotIn("store_id", sanitized["metadata"])
        self.assertEqual(sanitized["summary"], "ok")

    def test_build_request_uses_trusted_report_run_id_only(self) -> None:
        body = build_agent_output_request(
            report_run_id=VALID_REPORT_RUN_ID,
            node_name=WORKFLOW_NODE_RUN_SALES,
            specialist_output=_specialist_response("sales-agent"),
        )

        self.assertEqual(body["report_run_id"], VALID_REPORT_RUN_ID)
        self.assertEqual(body["output_type"], "sales_analysis")
        self.assertEqual(body["metadata"]["source_agent_name"], "sales-agent")
        self.assertEqual(body["metadata"]["coordinator_node"], WORKFLOW_NODE_RUN_SALES)
        self.assertNotIn("tenant_id", body["payload"])
        self.assertNotIn("store_id", body["payload"])


class SpecialistNodePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.django = _RecordingDjangoClient()
        self.specialist = _MockSpecialistClient()
        self.deps = WorkflowNodeDependencies(
            django_client=self.django,
            specialist_client_factory=lambda _timeout: self.specialist,
        )

    def test_sales_output_is_persisted(self) -> None:
        state = _base_state()
        state = node_run_sales(state, self.deps)

        self.assertIsNotNone(state.sales_output)
        self.assertEqual(len(state.agent_outputs_ref), 1)
        self.assertEqual(self.django.agent_output_calls[0]["output_type"], "sales_analysis")

    def test_content_output_is_persisted(self) -> None:
        state = _base_state()
        state = node_run_content(state, self.deps)

        self.assertIsNotNone(state.content_output)
        self.assertEqual(len(state.agent_outputs_ref), 1)
        self.assertEqual(
            self.django.agent_output_calls[0]["output_type"],
            "content_suggestions",
        )

    def test_support_output_is_persisted(self) -> None:
        state = _base_state()
        state = node_run_support(state, self.deps)

        self.assertIsNotNone(state.support_output)
        self.assertEqual(len(state.agent_outputs_ref), 1)
        self.assertEqual(
            self.django.agent_output_calls[0]["output_type"],
            "support_insights",
        )

    def test_persisted_ids_are_stored_in_coordinator_state(self) -> None:
        state = _base_state()
        state = node_run_sales(state, self.deps)
        state = node_run_content(state, self.deps)
        state = node_run_support(state, self.deps)

        self.assertEqual(len(state.agent_outputs_ref), 3)
        self.assertEqual(len(set(state.agent_outputs_ref)), 3)

    def test_merge_includes_agent_outputs_ref(self) -> None:
        state = _base_state()
        state = node_run_sales(state, self.deps)
        state = node_run_content(state, self.deps)
        state = node_run_support(state, self.deps)
        state = node_merge(state, self.deps)

        self.assertIsNotNone(state.merged_report)
        self.assertEqual(state.merged_report["agent_outputs_ref"], state.agent_outputs_ref)
        self.assertEqual(len(state.merged_report["agent_outputs_ref"]), 3)

    def test_submit_forwards_agent_output_ids(self) -> None:
        state = _base_state()
        state = node_run_sales(state, self.deps)
        state = node_merge(state, self.deps)
        state = node_submit(state, self.deps)

        self.assertEqual(len(self.django.submit_calls), 1)
        submit_call = self.django.submit_calls[0]
        self.assertEqual(submit_call["agent_output_ids"], state.agent_outputs_ref)
        self.assertEqual(
            submit_call["report"]["agent_outputs_ref"],
            state.agent_outputs_ref,
        )


class AgentOutputPersistenceFailureTests(unittest.TestCase):
    def test_persistence_failure_adds_warning_and_keeps_specialist_output(self) -> None:
        django = _RecordingDjangoClient(fail_nodes=frozenset({WORKFLOW_NODE_RUN_SALES}))
        specialist = _MockSpecialistClient()
        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=lambda _timeout: specialist,
        )

        state = _base_state()
        state = node_run_sales(state, deps)

        self.assertIsNotNone(state.sales_output)
        self.assertEqual(state.agent_outputs_ref, [])
        self.assertTrue(
            any(w.code == "agent_output_persistence_failed" for w in state.warnings),
        )
        warning = next(w for w in state.warnings if w.code == "agent_output_persistence_failed")
        self.assertNotIn("Bearer", warning.message)
        self.assertNotIn("service-jwt", warning.message)

    def test_persist_helper_returns_structured_failure_without_raising(self) -> None:
        class _FailingClient:
            def create_agent_output(self, payload: dict[str, Any]) -> dict[str, Any]:
                raise DjangoHTTPError(503, "Unavailable.")

        result = persist_specialist_agent_output(
            django_client=_FailingClient(),  # type: ignore[arg-type]
            report_run_id=VALID_REPORT_RUN_ID,
            node_name=WORKFLOW_NODE_RUN_SALES,
            specialist_output=_specialist_response("sales-agent"),
        )

        self.assertFalse(result.persisted)
        self.assertIsNone(result.agent_output_id)
        self.assertIsNotNone(result.warning)
        self.assertEqual(result.warning.code, "agent_output_persistence_failed")


class AgentOutputTimeoutBehaviorTests(unittest.TestCase):
    def test_timeout_skips_persistence_and_adds_not_persisted_warning(self) -> None:
        import time

        from agents.coordinator.config import CoordinatorNodeTimeouts
        from agents.coordinator.nodes import node_fetch_context

        class _SlowSpecialistClient(_MockSpecialistClient):
            def run_sales(self, payload: dict[str, Any]) -> dict[str, Any]:
                time.sleep(0.2)
                return super().run_sales(payload)

        django = _RecordingDjangoClient()
        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=lambda _timeout: _SlowSpecialistClient(),
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=0.05,
            ),
        )

        state = _base_state()
        state = node_fetch_context(state, deps)
        state = node_run_sales(state, deps)

        self.assertIsNone(state.sales_output)
        self.assertEqual(state.agent_outputs_ref, [])
        self.assertEqual(django.agent_output_calls, [])
        self.assertTrue(
            any(w.code == "agent_output_not_persisted" for w in state.warnings),
        )


class AgentOutputWorkflowIntegrationTests(unittest.TestCase):
    def test_full_workflow_collects_three_agent_output_refs(self) -> None:
        django = _RecordingDjangoClient()
        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=lambda _timeout: _MockSpecialistClient(),
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(result.agent_outputs_ref), 3)
        self.assertEqual(
            result.merged_report["agent_outputs_ref"],
            result.agent_outputs_ref,
        )
        self.assertEqual(
            django.submit_calls[0]["agent_output_ids"],
            result.agent_outputs_ref,
        )

    def test_django_client_receives_service_token_and_request_id_for_persistence(self) -> None:
        state = _base_state(service_token="coord-jwt", request_id="trace-xyz")
        deps = WorkflowNodeDependencies(
            specialist_client_factory=lambda _timeout: _MockSpecialistClient(),
        )

        with patch("agents.coordinator.nodes.DjangoClient") as mock_cls:
            mock_cls.return_value = _RecordingDjangoClient()
            node_run_sales(state, deps)

        mock_cls.assert_called()
        _, kwargs = mock_cls.call_args
        self.assertEqual(kwargs["service_token"], "coord-jwt")
        self.assertEqual(kwargs["request_id"], "trace-xyz")


if __name__ == "__main__":
    unittest.main()
