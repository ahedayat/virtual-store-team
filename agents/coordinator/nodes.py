"""Coordinator daily report workflow nodes with timeout boundaries (Step 10.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agents.coordinator.agent_output_persistence import (
    build_agent_output_not_persisted_warning,
    persist_specialist_agent_output,
)
from agents.coordinator.merge import build_merged_daily_report
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


def _base_specialist_payload(state: DailyReportWorkflowState) -> dict[str, Any]:
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
        "output_language": "en",
    }


def _sales_specialist_payload(state: DailyReportWorkflowState) -> dict[str, Any]:
    base = _base_specialist_payload(state)
    context = state.context if isinstance(state.context, dict) else {}
    payload = {
        "context": context,
        "store_id": state.store_id,
        "report_run_id": state.report_run_id,
        "request_id": state.request_id,
        "service_token": state.service_token,
        "fetch_from_django": base["fetch_from_django"],
        "persist_actions": base["persist_actions"],
        "dry_run": base["dry_run"],
        "output_language": base["output_language"],
    }
    sales_summary = context.get("sales_summary")
    if isinstance(sales_summary, dict):
        payload["sales_summary"] = sales_summary
    inventory = context.get("inventory")
    if isinstance(inventory, dict):
        payload["inventory"] = inventory
    return payload


def _content_specialist_payload(state: DailyReportWorkflowState) -> dict[str, Any]:
    base = _base_specialist_payload(state)
    context = state.context if isinstance(state.context, dict) else {}
    products_section = context.get("products")
    products: list[dict[str, Any]] = []
    if isinstance(products_section, dict):
        raw_items = products_section.get("items")
        if isinstance(raw_items, list):
            products = [item for item in raw_items if isinstance(item, dict)]

    store = context.get("store")
    store_context: dict[str, Any] = {"settings": {"brand_voice": {"tone": "warm"}}}
    if isinstance(store, dict):
        display_name = store.get("name")
        if isinstance(display_name, str) and display_name.strip():
            store_context["display_name"] = display_name.strip()
        settings = store.get("settings")
        if isinstance(settings, dict):
            store_context["settings"] = settings

    return {
        "context": context,
        "products": products,
        "store_context": store_context,
        "report_run_id": state.report_run_id,
        "request_id": state.request_id,
        "output_language": base["output_language"],
    }


def _derive_support_message_from_context(context: dict[str, Any]) -> tuple[str, str]:
    messages = context.get("messages")
    if isinstance(messages, dict):
        threads = messages.get("threads")
        if isinstance(threads, list):
            for thread in threads:
                if not isinstance(thread, dict):
                    continue
                channel = thread.get("channel")
                resolved_channel = (
                    channel.strip()
                    if isinstance(channel, str) and channel.strip()
                    else "instagram_dm"
                )
                raw_messages = thread.get("messages")
                if not isinstance(raw_messages, list):
                    continue
                for message in raw_messages:
                    if not isinstance(message, dict):
                        continue
                    sender_role = message.get("sender_role") or message.get("sender_type")
                    if sender_role != "customer":
                        continue
                    text = message.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip(), resolved_channel
    return "What are your store hours?", "instagram_dm"


def _support_specialist_payload(state: DailyReportWorkflowState) -> dict[str, Any]:
    base = _base_specialist_payload(state)
    context = state.context if isinstance(state.context, dict) else {}
    customer_message, channel = _derive_support_message_from_context(context)
    return {
        "tenant_id": state.tenant_id,
        "store_id": state.store_id,
        "context": context,
        "report_run_id": state.report_run_id,
        "request_id": state.request_id,
        "service_token": state.service_token,
        "customer_message": customer_message,
        "channel": channel,
        "fetch_recent_messages": False,
        "persist_actions": base["persist_actions"],
        "dry_run": base["dry_run"],
        "output_language": base["output_language"],
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


def _persist_specialist_output(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
    *,
    node_name: str,
    output: dict[str, Any],
) -> None:
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.timeout_for_node(node_name)
    client = deps.build_django_client(timeout_seconds, state)
    result = persist_specialist_agent_output(
        django_client=client,
        report_run_id=state.report_run_id,
        node_name=node_name,
        specialist_output=output,
    )
    if result.persisted and result.agent_output_id is not None:
        state.agent_outputs_ref.append(result.agent_output_id)
    elif result.warning is not None:
        state.warnings.append(result.warning)


def _run_specialist_node(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
    *,
    node_name: str,
    runner: Callable[[SpecialistAgentClient, dict[str, Any]], dict[str, Any]],
    output_field: str,
    payload_builder: Callable[[DailyReportWorkflowState], dict[str, Any]],
) -> DailyReportWorkflowState:
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.timeout_for_node(node_name)
    payload = payload_builder(state)

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
        _persist_specialist_output(state, deps, node_name=node_name, output=output)
    except CoordinatorNodeTimeoutError:
        state.warnings.append(
            build_specialist_timeout_warning(node_name, timeout_seconds=timeout_seconds)
        )
        state.warnings.append(build_agent_output_not_persisted_warning(node_name=node_name))
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
        payload_builder=_sales_specialist_payload,
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
        payload_builder=_content_specialist_payload,
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
        payload_builder=_support_specialist_payload,
    )


def node_merge(
    state: DailyReportWorkflowState,
    deps: WorkflowNodeDependencies,
) -> DailyReportWorkflowState:
    """Merge available specialist outputs into a partial or full report payload."""
    timeouts = deps.resolve_timeouts()
    timeout_seconds = timeouts.merge_seconds

    def _merge() -> dict[str, Any]:
        return build_merged_daily_report(
            report_run_id=state.report_run_id,
            store_id=state.store_id,
            context=state.context,
            sales_output=state.sales_output,
            content_output=state.content_output,
            support_output=state.support_output,
            agent_outputs_ref=list(state.agent_outputs_ref),
            workflow_warnings=list(state.warnings),
        )

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
            agent_output_ids=list(state.agent_outputs_ref) or None,
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
