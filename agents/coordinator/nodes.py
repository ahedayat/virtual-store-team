"""Coordinator daily report workflow nodes with timeout boundaries (Step 10.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agents.coordinator.config import CoordinatorNodeTimeouts, load_coordinator_node_timeouts
from agents.coordinator.specialist_clients import SpecialistAgentClient
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.timeout import (
    CoordinatorNodeTimeoutError,
    build_specialist_timeout_warning,
    run_with_node_timeout,
    sanitize_timeout_error_message,
)
from agents.coordinator.workflow import (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_SUBMIT,
)
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.base import AgentWarning

COORDINATOR_SERVICE_NAME = "coordinator-agent"


@dataclass
class WorkflowNodeDependencies:
    """Injectable dependencies for coordinator workflow node execution."""

    django_client: DjangoClient | None = None
    specialist_client_factory: Callable[[float], SpecialistAgentClient] | None = None
    node_timeouts: CoordinatorNodeTimeouts | None = None

    def resolve_timeouts(self) -> CoordinatorNodeTimeouts:
        return self.node_timeouts or load_coordinator_node_timeouts()

    def build_django_client(
        self,
        timeout_seconds: float,
        state: DailyReportWorkflowState,
    ) -> DjangoClient:
        if self.django_client is not None:
            return self.django_client
        return DjangoClient(
            timeout_seconds=timeout_seconds,
            service_token=state.service_token,
            request_id=state.request_id,
        )

    def build_specialist_client(
        self,
        timeout_seconds: float,
        state: DailyReportWorkflowState,
    ) -> SpecialistAgentClient:
        if self.specialist_client_factory is not None:
            return self.specialist_client_factory(timeout_seconds)
        return SpecialistAgentClient(
            timeout_seconds=timeout_seconds,
            service_token=state.service_token,
            request_id=state.request_id,
        )


def _specialist_payload(state: DailyReportWorkflowState) -> dict[str, Any]:
    return {
        "report_run_id": state.report_run_id,
        "tenant_id": state.tenant_id,
        "store_id": state.store_id,
        "context": state.context,
        "request_id": state.request_id,
        "service_token": state.service_token,
        "fetch_from_django": False,
        "persist_actions": False,
        "dry_run": True,
    }


def _mark_critical_failure(
    state: DailyReportWorkflowState,
    *,
    node_name: str,
    error: CoordinatorNodeTimeoutError,
) -> DailyReportWorkflowState:
    state.failed = True
    state.status = "failed"
    state.error_message = sanitize_timeout_error_message(
        node_name=node_name,
        critical=True,
    )
    state.warnings.append(
        AgentWarning(
            code="critical_node_timeout",
            message=state.error_message,
        )
    )
    return state


def node_fetch_context(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    """Fetch sanitized context from Django; critical — timeout fails the workflow."""
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.fetch_context_seconds

    def _fetch() -> dict[str, Any]:
        client = deps.build_django_client(timeout_seconds, state)
        return client.get_context_bundle(state.report_run_id)

    try:
        state.context = run_with_node_timeout(
            WORKFLOW_NODE_FETCH_CONTEXT,
            timeout_seconds,
            _fetch,
            report_run_id=state.report_run_id,
            service_name=COORDINATOR_SERVICE_NAME,
        )
    except CoordinatorNodeTimeoutError as exc:
        return _mark_critical_failure(state, node_name=WORKFLOW_NODE_FETCH_CONTEXT, error=exc)
    return state


def _run_specialist_node(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
    *,
    node_name: str,
    runner: Callable[[SpecialistAgentClient, dict[str, Any]], dict[str, Any]],
    output_field: str,
) -> DailyReportWorkflowState:
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.timeout_for_node(node_name)
    payload = _specialist_payload(state)

    def _call() -> dict[str, Any]:
        client = deps.build_specialist_client(timeout_seconds, state)
        return runner(client, payload)

    try:
        output = run_with_node_timeout(
            node_name,
            timeout_seconds,
            _call,
            report_run_id=state.report_run_id,
            service_name=node_name,
        )
        setattr(state, output_field, output)
    except CoordinatorNodeTimeoutError:
        state.warnings.append(
            build_specialist_timeout_warning(node_name, timeout_seconds=timeout_seconds)
        )
    return state


def node_run_sales(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    return _run_specialist_node(
        state,
        deps,
        node_name=WORKFLOW_NODE_RUN_SALES,
        runner=lambda client, payload: client.run_sales(payload),
        output_field="sales_output",
    )


def node_run_content(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    return _run_specialist_node(
        state,
        deps,
        node_name=WORKFLOW_NODE_RUN_CONTENT,
        runner=lambda client, payload: client.run_content(payload),
        output_field="content_output",
    )


def node_run_support(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    return _run_specialist_node(
        state,
        deps,
        node_name=WORKFLOW_NODE_RUN_SUPPORT,
        runner=lambda client, payload: client.run_support(payload),
        output_field="support_output",
    )


def _extract_section_summary(output: dict[str, Any] | None) -> dict[str, Any] | None:
    if output is None:
        return None
    summary = output.get("summary")
    if isinstance(summary, str) and summary.strip():
        return {"summary": summary.strip()}
    metadata = output.get("metadata")
    if isinstance(metadata, dict):
        agent_name = metadata.get("agent_name")
        if isinstance(agent_name, str) and agent_name.strip():
            return {"agent_name": agent_name.strip()}
    return {"present": True}


def node_merge(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    """Merge available specialist outputs into a partial or full report payload."""
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.merge_seconds

    def _merge() -> dict[str, Any]:
        sections: dict[str, Any] = {}
        missing_sections: list[str] = []

        for key, output in (
            ("sales", state.sales_output),
            ("content", state.content_output),
            ("support", state.support_output),
        ):
            section = _extract_section_summary(output)
            if section is None:
                missing_sections.append(key)
            else:
                sections[key] = section

        return {
            "report_run_id": state.report_run_id,
            "store_id": state.store_id,
            "sections": sections,
            "missing_sections": missing_sections,
            "partial": bool(missing_sections),
        }

    try:
        state.merged_report = run_with_node_timeout(
            WORKFLOW_NODE_MERGE,
            timeout_seconds,
            _merge,
            report_run_id=state.report_run_id,
            service_name=COORDINATOR_SERVICE_NAME,
        )
    except CoordinatorNodeTimeoutError as exc:
        return _mark_critical_failure(state, node_name=WORKFLOW_NODE_MERGE, error=exc)
    return state


def node_submit(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    """Submit merged report to Django; critical — timeout fails the workflow."""
    if state.merged_report is None:
        state.failed = True
        state.status = "failed"
        state.error_message = "Cannot submit daily report without merged content."
        return state

    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.submit_seconds

    def _submit() -> dict[str, Any]:
        client = deps.build_django_client(timeout_seconds, state)
        return client.complete_report_run(
            state.report_run_id,
            report=state.merged_report,
        )

    try:
        state.submit_result = run_with_node_timeout(
            WORKFLOW_NODE_SUBMIT,
            timeout_seconds,
            _submit,
            report_run_id=state.report_run_id,
            service_name=COORDINATOR_SERVICE_NAME,
        )
        state.status = "completed"
    except CoordinatorNodeTimeoutError as exc:
        return _mark_critical_failure(state, node_name=WORKFLOW_NODE_SUBMIT, error=exc)
    return state


WORKFLOW_NODE_EXECUTORS = {
    WORKFLOW_NODE_FETCH_CONTEXT: node_fetch_context,
    WORKFLOW_NODE_RUN_SALES: node_run_sales,
    WORKFLOW_NODE_RUN_CONTENT: node_run_content,
    WORKFLOW_NODE_RUN_SUPPORT: node_run_support,
    WORKFLOW_NODE_MERGE: node_merge,
    WORKFLOW_NODE_SUBMIT: node_submit,
}

__all__ = [
    "WORKFLOW_NODE_EXECUTORS",
    "WorkflowNodeDependencies",
    "node_fetch_context",
    "node_merge",
    "node_run_content",
    "node_run_sales",
    "node_run_support",
    "node_submit",
]
