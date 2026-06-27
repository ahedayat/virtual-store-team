"""Tests for LangGraph-backed coordinator workflow (Phase 10.6)."""

from __future__ import annotations

import time
import unittest
from typing import Any

from agents.coordinator.config import CoordinatorNodeTimeouts
from agents.coordinator.graph import (
    DAILY_REPORT_GRAPH_NODE_NAMES,
    build_daily_report_graph,
    invoke_daily_report_graph,
)
from agents.coordinator.nodes import WorkflowNodeDependencies
from agents.coordinator.runner import run_daily_report_workflow
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.tests.test_node_timeouts import (
    _MockDjangoClient,
    _MockSpecialistClient,
    _base_state,
)
from agents.coordinator.workflow import (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_SUBMIT,
)


class LangGraphCompilationTests(unittest.TestCase):
    def test_graph_compiles_successfully(self) -> None:
        graph = build_daily_report_graph()
        self.assertIsNotNone(graph)

    def test_graph_contains_planned_logical_nodes(self) -> None:
        graph = build_daily_report_graph()
        node_names = set(graph.get_graph().nodes.keys())
        for expected in DAILY_REPORT_GRAPH_NODE_NAMES:
            self.assertIn(expected, node_names)

    def test_graph_node_constants_match_workflow_nodes(self) -> None:
        self.assertEqual(
            DAILY_REPORT_GRAPH_NODE_NAMES,
            (
                WORKFLOW_NODE_FETCH_CONTEXT,
                WORKFLOW_NODE_RUN_SALES,
                WORKFLOW_NODE_RUN_CONTENT,
                WORKFLOW_NODE_RUN_SUPPORT,
                WORKFLOW_NODE_MERGE,
                WORKFLOW_NODE_SUBMIT,
            ),
        )


class LangGraphExecutionTests(unittest.TestCase):
    def test_graph_execution_succeeds_with_mock_clients(self) -> None:
        django = _MockDjangoClient()
        specialist = _MockSpecialistClient(
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )

        def factory(timeout: float) -> _MockSpecialistClient:
            specialist.timeout_seconds = timeout
            return specialist

        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=factory,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=1.0,
                content_seconds=1.0,
                support_seconds=1.0,
                merge_seconds=1.0,
                submit_seconds=1.0,
            ),
        )

        result = invoke_daily_report_graph(_base_state(), deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertEqual(django.context_calls, 1)
        self.assertEqual(django.submit_calls, 1)
        self.assertIsNotNone(result.merged_report)

    def test_runner_uses_graph_backed_workflow(self) -> None:
        django = _MockDjangoClient()
        specialist = _MockSpecialistClient(
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=lambda _timeout: specialist,
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertEqual(result.status, "completed")
        self.assertEqual(django.submit_calls, 1)


class LangGraphParallelExecutionTests(unittest.TestCase):
    def test_fast_specialist_completes_before_slow_specialist(self) -> None:
        completion_order: list[str] = []

        class _RecordingSpecialistClient(_MockSpecialistClient):
            def run_sales(self, payload: dict[str, Any]) -> dict[str, Any]:
                time.sleep(0.2)
                completion_order.append("sales")
                return super().run_sales(payload)

            def run_content(self, payload: dict[str, Any]) -> dict[str, Any]:
                time.sleep(0.01)
                completion_order.append("content")
                return super().run_content(payload)

            def run_support(self, payload: dict[str, Any]) -> dict[str, Any]:
                time.sleep(0.01)
                completion_order.append("support")
                return super().run_support(payload)

        specialist = _RecordingSpecialistClient(
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=lambda _timeout: specialist,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=2.0,
                sales_seconds=2.0,
                content_seconds=2.0,
                support_seconds=2.0,
                merge_seconds=2.0,
                submit_seconds=2.0,
            ),
        )

        started = time.monotonic()
        result = run_daily_report_workflow(_base_state(), deps)
        elapsed = time.monotonic() - started

        self.assertEqual(result.status, "completed")
        self.assertIn("content", completion_order)
        self.assertIn("sales", completion_order)
        content_index = completion_order.index("content")
        sales_index = completion_order.index("sales")
        self.assertLess(content_index, sales_index)
        self.assertLess(elapsed, 0.35)

    def test_parallel_specialists_do_not_block_each_other_beyond_fan_in(self) -> None:
        delays = {"sales": 0.15, "content": 0.15, "support": 0.15}
        specialist = _MockSpecialistClient(
            delays_by_agent=delays,
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=lambda _timeout: specialist,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=2.0,
                sales_seconds=2.0,
                content_seconds=2.0,
                support_seconds=2.0,
                merge_seconds=2.0,
                submit_seconds=2.0,
            ),
        )

        started = time.monotonic()
        result = run_daily_report_workflow(_base_state(), deps)
        elapsed = time.monotonic() - started

        self.assertEqual(result.status, "completed")
        self.assertLess(elapsed, 0.35)


class LangGraphTimeoutPreservationTests(unittest.TestCase):
    def test_critical_fetch_timeout_fails_under_graph_execution(self) -> None:
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(context_delay=0.2),
            node_timeouts=CoordinatorNodeTimeouts(fetch_context_seconds=0.05),
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertTrue(result.failed)
        self.assertEqual(result.status, "failed")
        self.assertTrue(any(w.code == "critical_node_timeout" for w in result.warnings))

    def test_specialist_timeout_produces_warnings_under_graph_execution(self) -> None:
        specialist = _MockSpecialistClient(
            delays_by_agent={"sales": 0.2},
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=lambda _timeout: specialist,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=0.05,
                content_seconds=1.0,
                support_seconds=1.0,
                merge_seconds=1.0,
                submit_seconds=1.0,
            ),
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertIsNone(result.sales_output)
        report = result.merged_report
        assert report is not None
        self.assertIn("sales", report["missing_sections"])
        codes = {warning.code for warning in result.warnings}
        self.assertIn("specialist_node_timeout", codes)
        self.assertIn("agent_output_not_persisted", codes)


class LangGraphAgentOutputPersistenceTests(unittest.TestCase):
    def test_agent_output_ids_collected_under_graph_execution(self) -> None:
        django = _MockDjangoClient()
        specialist = _MockSpecialistClient(
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=lambda _timeout: specialist,
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertEqual(len(result.agent_outputs_ref), 3)
        self.assertEqual(django.agent_output_calls, 3)
        report = result.merged_report
        assert report is not None
        self.assertEqual(report["agent_outputs_ref"], result.agent_outputs_ref)


class LangGraphPartialFailureTests(unittest.TestCase):
    def test_partial_specialist_failure_produces_structured_warnings(self) -> None:
        specialist = _MockSpecialistClient(
            delays_by_agent={"support": 0.2},
            response={"summary": "ok", "metadata": {"agent_name": "sales-agent"}},
        )
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=lambda _timeout: specialist,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=1.0,
                content_seconds=1.0,
                support_seconds=0.05,
                merge_seconds=1.0,
                submit_seconds=1.0,
            ),
        )

        result = run_daily_report_workflow(_base_state(), deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertIsNone(result.support_output)
        self.assertIsNotNone(result.sales_output)
        self.assertIsNotNone(result.content_output)
        report = result.merged_report
        assert report is not None
        self.assertTrue(report["partial"])
        self.assertIn("support", report["missing_sections"])
        self.assertTrue(
            any(warning.code == "specialist_node_timeout" for warning in result.warnings),
        )


if __name__ == "__main__":
    unittest.main()
