"""Coordinator daily report workflow runner (Step 10.2, graph-backed in 10.6)."""

from __future__ import annotations

from agents.coordinator.graph import invoke_daily_report_graph
from agents.coordinator.nodes import WORKFLOW_NODE_EXECUTORS, WorkflowNodeDependencies
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.workflow import DAILY_REPORT_WORKFLOW_NODES


def run_daily_report_workflow(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies | None = None,
) -> DailyReportWorkflowState:
    """Execute the LangGraph-backed coordinator workflow with timeout boundaries."""
    return invoke_daily_report_graph(state, deps)


def list_workflow_node_executors() -> tuple[str, ...]:
    """Return workflow node names that have executable handlers."""
    return tuple(
        node_name
        for node_name in DAILY_REPORT_WORKFLOW_NODES
        if node_name in WORKFLOW_NODE_EXECUTORS
    )
