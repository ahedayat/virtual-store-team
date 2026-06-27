"""LangGraph daily-report workflow with parallel specialist fan-out (Step 10.6)."""

from __future__ import annotations

import operator
from dataclasses import fields
from typing import Annotated, Any, Callable

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from agents.coordinator.nodes import (
    WorkflowNodeDependencies,
    node_fetch_context,
    node_merge,
    node_run_content,
    node_run_sales,
    node_run_support,
    node_submit,
)
from agents.coordinator.state import DailyReportWorkflowState
from agents.coordinator.workflow import (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_SUBMIT,
)
from agents.shared.schemas.base import AgentWarning

_GRAPH_REDUCER_FIELDS = frozenset({"warnings", "agent_outputs_ref"})


class DailyReportGraphState(TypedDict, total=False):
    """LangGraph state schema compatible with ``DailyReportWorkflowState``."""

    report_run_id: str
    tenant_id: str
    store_id: str
    service_token: str | None
    request_id: str | None
    context: dict[str, Any] | None
    sales_output: dict[str, Any] | None
    content_output: dict[str, Any] | None
    support_output: dict[str, Any] | None
    agent_outputs_ref: Annotated[list[str], operator.add]
    merged_report: dict[str, Any] | None
    submit_result: dict[str, Any] | None
    warnings: Annotated[list[AgentWarning], operator.add]
    failed: bool
    error_message: str | None
    status: str


DAILY_REPORT_GRAPH_NODE_NAMES: tuple[str, ...] = (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_SUBMIT,
)


def workflow_state_to_graph_state(
    state: DailyReportWorkflowState,
) -> DailyReportGraphState:
    return DailyReportGraphState(
        report_run_id=state.report_run_id,
        tenant_id=state.tenant_id,
        store_id=state.store_id,
        service_token=state.service_token,
        request_id=state.request_id,
        context=state.context,
        sales_output=state.sales_output,
        content_output=state.content_output,
        support_output=state.support_output,
        agent_outputs_ref=list(state.agent_outputs_ref),
        merged_report=state.merged_report,
        submit_result=state.submit_result,
        warnings=list(state.warnings),
        failed=state.failed,
        error_message=state.error_message,
        status=state.status,
    )


def graph_state_to_workflow_state(
    graph_state: DailyReportGraphState,
) -> DailyReportWorkflowState:
    return DailyReportWorkflowState(
        report_run_id=graph_state["report_run_id"],
        tenant_id=graph_state["tenant_id"],
        store_id=graph_state["store_id"],
        service_token=graph_state.get("service_token"),
        request_id=graph_state.get("request_id"),
        context=graph_state.get("context"),
        sales_output=graph_state.get("sales_output"),
        content_output=graph_state.get("content_output"),
        support_output=graph_state.get("support_output"),
        agent_outputs_ref=list(graph_state.get("agent_outputs_ref") or []),
        merged_report=graph_state.get("merged_report"),
        submit_result=graph_state.get("submit_result"),
        warnings=list(graph_state.get("warnings") or []),
        failed=bool(graph_state.get("failed")),
        error_message=graph_state.get("error_message"),
        status=graph_state.get("status", "running"),
    )


def clone_workflow_state(state: DailyReportWorkflowState) -> DailyReportWorkflowState:
    """Return a shallow copy safe for in-place node mutation."""
    return DailyReportWorkflowState(
        report_run_id=state.report_run_id,
        tenant_id=state.tenant_id,
        store_id=state.store_id,
        service_token=state.service_token,
        request_id=state.request_id,
        context=state.context.copy() if isinstance(state.context, dict) else state.context,
        sales_output=(
            state.sales_output.copy() if isinstance(state.sales_output, dict) else state.sales_output
        ),
        content_output=(
            state.content_output.copy()
            if isinstance(state.content_output, dict)
            else state.content_output
        ),
        support_output=(
            state.support_output.copy()
            if isinstance(state.support_output, dict)
            else state.support_output
        ),
        agent_outputs_ref=list(state.agent_outputs_ref),
        merged_report=(
            state.merged_report.copy() if isinstance(state.merged_report, dict) else state.merged_report
        ),
        submit_result=(
            state.submit_result.copy() if isinstance(state.submit_result, dict) else state.submit_result
        ),
        warnings=list(state.warnings),
        failed=state.failed,
        error_message=state.error_message,
        status=state.status,
    )


def _list_delta(before: list[Any], after: list[Any]) -> list[Any]:
    if len(after) <= len(before):
        return []
    return after[len(before) :]


def _workflow_state_delta(
    before: DailyReportWorkflowState,
    after: DailyReportWorkflowState,
) -> DailyReportGraphState:
    update: DailyReportGraphState = {}
    for field in fields(DailyReportWorkflowState):
        before_value = getattr(before, field.name)
        after_value = getattr(after, field.name)
        if field.name in _GRAPH_REDUCER_FIELDS:
            delta = _list_delta(before_value, after_value)
            if delta:
                update[field.name] = delta  # type: ignore[literal-required]
            continue
        if before_value != after_value:
            update[field.name] = after_value  # type: ignore[literal-required]
    return update


def _wrap_workflow_node(
    node_fn: Callable[[DailyReportWorkflowState, WorkflowNodeDependencies], DailyReportWorkflowState],
    deps: WorkflowNodeDependencies,
) -> Callable[[DailyReportGraphState], DailyReportGraphState]:
    def _graph_node(graph_state: DailyReportGraphState) -> DailyReportGraphState:
        before = graph_state_to_workflow_state(graph_state)
        working = clone_workflow_state(before)
        after = node_fn(working, deps)
        return _workflow_state_delta(before, after)

    return _graph_node


def _route_after_fetch_context(state: DailyReportGraphState) -> str | list[str]:
    if state.get("failed"):
        return END
    return [
        WORKFLOW_NODE_RUN_SALES,
        WORKFLOW_NODE_RUN_CONTENT,
        WORKFLOW_NODE_RUN_SUPPORT,
    ]


def _route_after_merge(state: DailyReportGraphState) -> str:
    if state.get("failed"):
        return END
    return WORKFLOW_NODE_SUBMIT


def build_daily_report_graph(
    deps: WorkflowNodeDependencies | None = None,
):
    """Compile the coordinator daily-report LangGraph workflow."""
    dependencies = deps or WorkflowNodeDependencies()
    builder = StateGraph(DailyReportGraphState)

    builder.add_node(
        WORKFLOW_NODE_FETCH_CONTEXT,
        _wrap_workflow_node(node_fetch_context, dependencies),
    )
    builder.add_node(
        WORKFLOW_NODE_RUN_SALES,
        _wrap_workflow_node(node_run_sales, dependencies),
    )
    builder.add_node(
        WORKFLOW_NODE_RUN_CONTENT,
        _wrap_workflow_node(node_run_content, dependencies),
    )
    builder.add_node(
        WORKFLOW_NODE_RUN_SUPPORT,
        _wrap_workflow_node(node_run_support, dependencies),
    )
    builder.add_node(
        WORKFLOW_NODE_MERGE,
        _wrap_workflow_node(node_merge, dependencies),
    )
    builder.add_node(
        WORKFLOW_NODE_SUBMIT,
        _wrap_workflow_node(node_submit, dependencies),
    )

    builder.add_edge(START, WORKFLOW_NODE_FETCH_CONTEXT)
    builder.add_conditional_edges(
        WORKFLOW_NODE_FETCH_CONTEXT,
        _route_after_fetch_context,
        [
            WORKFLOW_NODE_RUN_SALES,
            WORKFLOW_NODE_RUN_CONTENT,
            WORKFLOW_NODE_RUN_SUPPORT,
            END,
        ],
    )
    builder.add_edge(WORKFLOW_NODE_RUN_SALES, WORKFLOW_NODE_MERGE)
    builder.add_edge(WORKFLOW_NODE_RUN_CONTENT, WORKFLOW_NODE_MERGE)
    builder.add_edge(WORKFLOW_NODE_RUN_SUPPORT, WORKFLOW_NODE_MERGE)
    builder.add_conditional_edges(
        WORKFLOW_NODE_MERGE,
        _route_after_merge,
        [WORKFLOW_NODE_SUBMIT, END],
    )
    builder.add_edge(WORKFLOW_NODE_SUBMIT, END)

    return builder.compile()


def invoke_daily_report_graph(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies | None = None,
) -> DailyReportWorkflowState:
    """Run the compiled LangGraph workflow and return coordinator workflow state."""
    graph = build_daily_report_graph(deps)
    graph_state = workflow_state_to_graph_state(state)
    result = graph.invoke(graph_state)
    return graph_state_to_workflow_state(result)


__all__ = [
    "DAILY_REPORT_GRAPH_NODE_NAMES",
    "DailyReportGraphState",
    "build_daily_report_graph",
    "clone_workflow_state",
    "graph_state_to_workflow_state",
    "invoke_daily_report_graph",
    "workflow_state_to_graph_state",
]
