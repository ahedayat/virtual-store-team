"""Helpers for the real daily-report workflow HTTP endpoint (Step 10.5)."""

from __future__ import annotations

import logging
from typing import Any

from agents.coordinator.app.schemas import DailyReportJobRequest, DailyReportWorkflowResponse
from agents.coordinator.nodes import WorkflowNodeDependencies
from agents.coordinator.runner import run_daily_report_workflow
from agents.coordinator.state import DailyReportWorkflowState

WORKFLOW_DAILY_REPORT = "daily_report"
COMPLETED_MESSAGE = "Daily report workflow completed."
FAILED_MESSAGE = "Daily report workflow failed."
UNEXPECTED_FAILURE_MESSAGE = "Daily report workflow failed unexpectedly."

logger = logging.getLogger(__name__)


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None


def build_workflow_state_from_request(
    payload: DailyReportJobRequest,
    *,
    service_token: str | None,
    request_id: str | None,
) -> DailyReportWorkflowState:
    return DailyReportWorkflowState(
        report_run_id=str(payload.report_run_id),
        tenant_id=str(payload.tenant_id),
        store_id=str(payload.store_id),
        service_token=service_token,
        request_id=request_id,
    )


def build_workflow_response(
    payload: DailyReportJobRequest,
    result_state: DailyReportWorkflowState,
) -> DailyReportWorkflowResponse:
    partial = False
    if isinstance(result_state.merged_report, dict):
        partial = bool(result_state.merged_report.get("partial"))

    if result_state.failed or result_state.status == "failed":
        message = result_state.error_message or FAILED_MESSAGE
        return DailyReportWorkflowResponse(
            status="failed",
            workflow=WORKFLOW_DAILY_REPORT,
            report_run_id=str(payload.report_run_id),
            message=message,
            warnings=list(result_state.warnings),
            partial=partial,
        )

    return DailyReportWorkflowResponse(
        status="completed",
        workflow=WORKFLOW_DAILY_REPORT,
        report_run_id=str(payload.report_run_id),
        message=COMPLETED_MESSAGE,
        warnings=list(result_state.warnings),
        partial=partial,
    )


def execute_daily_report_workflow(
    payload: DailyReportJobRequest,
    *,
    service_token: str | None,
    request_id: str | None,
    deps: WorkflowNodeDependencies | None = None,
) -> DailyReportWorkflowResponse:
    state = build_workflow_state_from_request(
        payload,
        service_token=service_token,
        request_id=request_id,
    )
    try:
        result_state = run_daily_report_workflow(state, deps)
    except Exception:
        logger.error(
            "Daily report workflow raised an unexpected error",
            extra={
                "report_run_id": str(payload.report_run_id),
                "request_id": request_id,
            },
        )
        return DailyReportWorkflowResponse(
            status="failed",
            workflow=WORKFLOW_DAILY_REPORT,
            report_run_id=str(payload.report_run_id),
            message=UNEXPECTED_FAILURE_MESSAGE,
            warnings=[],
            partial=False,
        )
    return build_workflow_response(payload, result_state)


def log_request_context(
    *,
    report_run_id: str,
    tenant_id: str,
    store_id: str,
    authorization: str | None,
    request_id: str | None,
) -> None:
    auth_present = bool(authorization)
    auth_scheme = None
    if authorization:
        scheme = authorization.split(" ", 1)[0]
        auth_scheme = scheme if scheme else None

    logger.info(
        "Daily report workflow request received",
        extra={
            "report_run_id": report_run_id,
            "tenant_id": tenant_id,
            "store_id": store_id,
            "auth_present": auth_present,
            "auth_scheme": auth_scheme,
            "request_id": request_id,
        },
    )
