"""Tests for coordinator per-node timeout handling (Phase 10.2)."""

from __future__ import annotations

import ast
import importlib
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from agents.coordinator.config import (
    DEFAULT_CONTENT_TIMEOUT_SECONDS,
    DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS,
    DEFAULT_MERGE_TIMEOUT_SECONDS,
    DEFAULT_SALES_TIMEOUT_SECONDS,
    DEFAULT_SUBMIT_TIMEOUT_SECONDS,
    DEFAULT_SUPPORT_TIMEOUT_SECONDS,
    CoordinatorNodeTimeouts,
    load_coordinator_node_timeouts,
)
from agents.coordinator.nodes import (
    WorkflowNodeDependencies,
    node_fetch_context,
    node_merge,
    node_run_sales,
    node_submit,
)
from agents.coordinator.runner import list_workflow_node_executors, run_daily_report_workflow
from agents.coordinator.specialist_clients import SpecialistAgentClient
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.timeout import (
    CoordinatorNodeTimeoutError,
    build_specialist_timeout_warning,
    run_with_node_timeout,
    sanitize_timeout_error_message,
)
from agents.coordinator import nodes as coordinator_nodes
from agents.coordinator import specialist_clients, topology
from agents.coordinator.workflow import (
    DAILY_REPORT_WORKFLOW_NODES,
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_RUN_SALES,
)
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.base import AgentWarning

REPO_ROOT = Path(__file__).resolve().parents[2]


class _SlowOperation:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    def __call__(self) -> str:
        time.sleep(self.delay_seconds)
        return "done"


class _MockDjangoClient:
    def __init__(
        self,
        *,
        context_delay: float = 0.0,
        submit_delay: float = 0.0,
        context_payload: dict[str, Any] | None = None,
        submit_payload: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.context_delay = context_delay
        self.submit_delay = submit_delay
        self.context_payload = context_payload or {"report_run_id": "run-1", "store": {}}
        self.submit_payload = submit_payload or {"status": "completed"}
        self.timeout_seconds = timeout_seconds
        self.context_calls = 0
        self.submit_calls = 0

    def get_context_bundle(self, report_run_id: str) -> dict[str, Any]:
        self.context_calls += 1
        if self.context_delay:
            time.sleep(self.context_delay)
        return {**self.context_payload, "report_run_id": report_run_id}

    def complete_report_run(
        self,
        report_run_id: str,
        *,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        self.submit_calls += 1
        if self.submit_delay:
            time.sleep(self.submit_delay)
        return {**self.submit_payload, "report_run_id": report_run_id}


class _MockSpecialistClient:
    def __init__(
        self,
        *,
        delay_seconds: float = 0.0,
        response: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        delays_by_agent: dict[str, float] | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.response = response or {
            "summary": "ok",
            "metadata": {"agent_name": "specialist-agent"},
        }
        self.timeout_seconds = timeout_seconds
        self.delays_by_agent = delays_by_agent or {}
        self.calls = 0

    def _run(self, agent: str) -> dict[str, Any]:
        self.calls += 1
        delay = self.delays_by_agent.get(agent, self.delay_seconds)
        if delay:
            time.sleep(delay)
        if isinstance(self.response, dict):
            metadata = self.response.get("metadata")
            if isinstance(metadata, dict):
                metadata = {**metadata, "agent_name": f"{agent}-agent"}
            return {**self.response, "metadata": metadata}
        return self.response

    def run_sales(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("sales")

    def run_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("content")

    def run_support(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("support")


def _base_state(**overrides: object) -> DailyReportWorkflowState:
    defaults: dict[str, Any] = {
        "report_run_id": "11111111-1111-4111-8111-111111111111",
        "tenant_id": "22222222-2222-4222-8222-222222222222",
        "store_id": "33333333-3333-4333-8333-333333333333",
        "service_token": "service-jwt",
        "request_id": "req-timeout-test",
    }
    defaults.update(overrides)
    return DailyReportWorkflowState(**defaults)


class CoordinatorTimeoutConfigTests(unittest.TestCase):
    def test_loads_safe_defaults(self) -> None:
        timeouts = load_coordinator_node_timeouts(env={})

        self.assertEqual(timeouts.fetch_context_seconds, DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.sales_seconds, DEFAULT_SALES_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.content_seconds, DEFAULT_CONTENT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.support_seconds, DEFAULT_SUPPORT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.merge_seconds, DEFAULT_MERGE_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.submit_seconds, DEFAULT_SUBMIT_TIMEOUT_SECONDS)

    def test_invalid_env_values_fall_back_to_defaults(self) -> None:
        env = {
            "COORDINATOR_FETCH_CONTEXT_TIMEOUT_SECONDS": "0",
            "COORDINATOR_SALES_TIMEOUT_SECONDS": "-5",
            "COORDINATOR_CONTENT_TIMEOUT_SECONDS": "not-a-number",
            "COORDINATOR_SUPPORT_TIMEOUT_SECONDS": "",
            "COORDINATOR_MERGE_TIMEOUT_SECONDS": "abc",
            "COORDINATOR_SUBMIT_TIMEOUT_SECONDS": "0.0",
        }
        timeouts = load_coordinator_node_timeouts(env=env)

        self.assertEqual(timeouts.fetch_context_seconds, DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.sales_seconds, DEFAULT_SALES_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.content_seconds, DEFAULT_CONTENT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.support_seconds, DEFAULT_SUPPORT_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.merge_seconds, DEFAULT_MERGE_TIMEOUT_SECONDS)
        self.assertEqual(timeouts.submit_seconds, DEFAULT_SUBMIT_TIMEOUT_SECONDS)

    def test_valid_env_overrides_defaults(self) -> None:
        env = {
            "COORDINATOR_FETCH_CONTEXT_TIMEOUT_SECONDS": "45",
            "COORDINATOR_SALES_TIMEOUT_SECONDS": "90",
        }
        timeouts = load_coordinator_node_timeouts(env=env)

        self.assertEqual(timeouts.fetch_context_seconds, 45.0)
        self.assertEqual(timeouts.sales_seconds, 90.0)


class CoordinatorTimeoutHelperTests(unittest.TestCase):
    def test_node_completes_before_timeout(self) -> None:
        result = run_with_node_timeout(
            "test_node",
            1.0,
            lambda: "success",
            report_run_id="run-fast",
        )
        self.assertEqual(result, "success")

    def test_node_exceeds_timeout_raises_structured_error(self) -> None:
        with self.assertRaises(CoordinatorNodeTimeoutError) as ctx:
            run_with_node_timeout(
                "slow_node",
                0.05,
                _SlowOperation(0.2),
                report_run_id="run-slow",
            )

        error = ctx.exception
        self.assertEqual(error.node_name, "slow_node")
        self.assertEqual(error.timeout_seconds, 0.05)
        self.assertIsNotNone(error.duration_ms)
        self.assertIn("slow_node", str(error))
        self.assertNotIn("service-jwt", str(error))

    def test_sanitize_timeout_error_message_is_safe(self) -> None:
        message = sanitize_timeout_error_message(
            node_name=WORKFLOW_NODE_FETCH_CONTEXT,
            critical=True,
        )
        self.assertIn(WORKFLOW_NODE_FETCH_CONTEXT, message)
        self.assertNotIn("Bearer", message)
        self.assertNotIn("prompt", message.lower())


class CoordinatorNodeTimeoutBehaviorTests(unittest.TestCase):
    def test_fetch_context_timeout_fails_safely(self) -> None:
        state = _base_state()
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(context_delay=0.2),
            node_timeouts=CoordinatorNodeTimeouts(fetch_context_seconds=0.05),
        )

        result = node_fetch_context(state, deps)

        self.assertTrue(result.failed)
        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.context)
        self.assertIsNotNone(result.error_message)
        self.assertTrue(
            any(w.code == "critical_node_timeout" for w in result.warnings),
        )

    def test_specialist_timeout_adds_warning_and_allows_partial_merge(self) -> None:
        state = _base_state()
        sales_client = _MockSpecialistClient(delay_seconds=0.2)
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=lambda _timeout: sales_client,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=0.05,
                merge_seconds=1.0,
            ),
        )

        state = node_fetch_context(state, deps)
        state = node_run_sales(state, deps)
        state = node_merge(state, deps)

        self.assertFalse(state.failed)
        self.assertIsNone(state.sales_output)
        self.assertIsNotNone(state.merged_report)
        self.assertIn("sales", state.merged_report["missing_sections"])
        self.assertTrue(state.merged_report["partial"])
        self.assertEqual(len(state.warnings), 1)
        self.assertEqual(state.warnings[0].code, "specialist_node_timeout")

    def test_partial_workflow_continues_when_specialist_times_out(self) -> None:
        state = _base_state()
        django = _MockDjangoClient()
        specialist = _MockSpecialistClient(
            delays_by_agent={"sales": 0.2},
            response={"summary": "section ok", "metadata": {"agent_name": "agent"}},
        )

        def factory(timeout: float) -> _MockSpecialistClient:
            specialist.timeout_seconds = timeout
            return specialist

        deps = WorkflowNodeDependencies(
            django_client=django,
            specialist_client_factory=factory,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=0.05,
                content_seconds=1.0,
                support_seconds=1.0,
                merge_seconds=1.0,
                submit_seconds=1.0,
            ),
        )

        result = run_daily_report_workflow(state, deps)

        self.assertFalse(result.failed)
        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.merged_report)
        self.assertIn("sales", result.merged_report["missing_sections"])
        self.assertNotIn("content", result.merged_report["missing_sections"])
        self.assertNotIn("support", result.merged_report["missing_sections"])
        self.assertEqual(django.submit_calls, 1)

    def test_submit_timeout_fails_safely(self) -> None:
        state = _base_state(
            context={"report_run_id": "run-1"},
            merged_report={"sections": {}, "missing_sections": [], "partial": False},
        )
        state.merged_report = {
            "report_run_id": state.report_run_id,
            "sections": {"sales": {"summary": "ok"}},
            "missing_sections": [],
            "partial": False,
        }
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(submit_delay=0.2),
            node_timeouts=CoordinatorNodeTimeouts(submit_seconds=0.05),
        )

        result = node_submit(state, deps)

        self.assertTrue(result.failed)
        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.submit_result)
        self.assertIn("submit", result.error_message or "")


class CoordinatorHttpTimeoutIntegrationTests(unittest.TestCase):
    def test_django_client_receives_configured_timeout(self) -> None:
        state = _base_state()
        deps = WorkflowNodeDependencies(
            node_timeouts=CoordinatorNodeTimeouts(fetch_context_seconds=42.0),
        )

        with patch("agents.coordinator.nodes.DjangoClient") as mock_cls:
            mock_cls.return_value = _MockDjangoClient()
            deps.build_django_client(42.0, state)

        mock_cls.assert_called_once_with(
            timeout_seconds=42.0,
            service_token=state.service_token,
            request_id=state.request_id,
        )

    def test_specialist_client_receives_configured_timeout(self) -> None:
        captured: list[float] = []

        def factory(timeout_seconds: float) -> SpecialistAgentClient:
            captured.append(timeout_seconds)
            transport = httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={"summary": "sales ok", "metadata": {"agent_name": "sales-agent"}},
                )
            )
            http_client = httpx.Client(transport=transport)
            return SpecialistAgentClient(http_client=http_client, timeout_seconds=timeout_seconds)

        state = _base_state(context={"store": {}})
        deps = WorkflowNodeDependencies(
            django_client=_MockDjangoClient(),
            specialist_client_factory=factory,
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=1.0,
                sales_seconds=77.0,
            ),
        )

        state = node_fetch_context(state, deps)
        state = node_run_sales(state, deps)

        self.assertEqual(captured, [77.0])
        self.assertEqual(
            state.sales_output,
            {"summary": "sales ok", "metadata": {"agent_name": "sales-agent"}},
        )

    def test_specialist_httpx_client_uses_timeout_from_constructor(self) -> None:
        client = SpecialistAgentClient(timeout_seconds=55.0)
        self.assertEqual(client.timeout_seconds, 55.0)


class CoordinatorStarTopologyPreservationTests(unittest.TestCase):
    def test_all_workflow_nodes_have_executors(self) -> None:
        executors = list_workflow_node_executors()
        self.assertEqual(executors, DAILY_REPORT_WORKFLOW_NODES)

    def test_nodes_module_does_not_import_specialist_business_internals(self) -> None:
        forbidden_prefixes = (
            "agents.sales.analysis",
            "agents.content.analysis",
            "agents.support.analysis",
        )
        source_path = Path(coordinator_nodes.__file__).resolve()
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        for forbidden in forbidden_prefixes:
            self.assertNotIn(forbidden, imported_modules)

    def test_specialist_peer_paths_remain_empty(self) -> None:
        topology.assert_star_topology()
        self.assertEqual(topology.SPECIALIST_PEER_CALL_PATHS, frozenset())

    def test_nodes_use_specialist_client_not_peer_urls(self) -> None:
        source = Path(coordinator_nodes.__file__).read_text(encoding="utf-8")
        self.assertIn("SpecialistAgentClient", source)
        self.assertNotIn("CONTENT_AGENT_URL", source)
        self.assertNotIn("SUPPORT_AGENT_URL", source)


class CoordinatorTimeoutWarningTests(unittest.TestCase):
    def test_specialist_timeout_warning_shape(self) -> None:
        warning = build_specialist_timeout_warning(
            WORKFLOW_NODE_RUN_SALES,
            timeout_seconds=60.0,
        )
        self.assertIsInstance(warning, AgentWarning)
        self.assertEqual(warning.code, "specialist_node_timeout")
        self.assertIn("sales", warning.message)
        self.assertNotIn("Bearer", warning.message)


if __name__ == "__main__":
    unittest.main()
