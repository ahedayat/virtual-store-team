"""Sequential coordinator daily report workflow runner (Step 10.2)."""

from __future__ import annotations

from agents.coordinator.nodes import (
    WORKFLOW_NODE_EXECUTORS,
    WorkflowNodeDependencies,
    node_fetch_context,
    node_merge,
    node_run_content,
    node_run_sales,
    node_run_support,
    node_submit,
)
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.workflow import DAILY_REPORT_WORKFLOW_NODES


def run_daily_report_workflow(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies | None = None,
) -> DailyReportWorkflowState:
    """Execute coordinator workflow nodes in star-topology order with timeout boundaries."""
    dependencies = deps or WorkflowNodeDependencies()

    state = node_fetch_context(state, dependencies)
    if state.failed:
        return state

    state = node_run_sales(state, dependencies)
    state = node_run_content(state, dependencies)
    state = node_run_support(state, dependencies)

    state = node_merge(state, dependencies)
    if state.failed:
        return state

    return node_submit(state, dependencies)


def list_workflow_node_executors() -> tuple[str, ...]:
    """Return workflow node names that have executable handlers."""
    return tuple(
        node_name
        for node_name in DAILY_REPORT_WORKFLOW_NODES
        if node_name in WORKFLOW_NODE_EXECUTORS
    )
