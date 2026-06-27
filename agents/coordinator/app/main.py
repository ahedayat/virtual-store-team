"""Coordinator-agent FastAPI application."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, HTTPException

from agents.coordinator.app.schemas import DailyReportJobRequest, DailyReportWorkflowResponse
from agents.coordinator.app.workflow_endpoint import (
    execute_daily_report_workflow,
    extract_bearer_token,
    log_request_context,
)

SERVICE_NAME = "coordinator-agent"

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}


@app.post("/workflows/daily-report", response_model=DailyReportWorkflowResponse)
def trigger_daily_report_workflow(
    payload: DailyReportJobRequest,
    authorization: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> DailyReportWorkflowResponse:
    """Run the coordinator daily-report workflow and submit completion via Django."""
    correlation_id = x_request_id or payload.request_id
    log_request_context(
        report_run_id=str(payload.report_run_id),
        tenant_id=str(payload.tenant_id),
        store_id=str(payload.store_id),
        authorization=authorization,
        request_id=correlation_id,
    )

    if authorization is not None and not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use Bearer scheme.",
        )

    service_token = extract_bearer_token(authorization)
    return execute_daily_report_workflow(
        payload,
        service_token=service_token,
        request_id=correlation_id,
    )
