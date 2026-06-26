"""Coordinator-agent FastAPI application (Phase 6.4 stub)."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException

from agents.coordinator.app.schemas import DailyReportJobRequest, DailyReportStubResponse
from agents.shared.schemas.base import AgentWarning

SERVICE_NAME = "coordinator-agent"
WORKFLOW_DAILY_REPORT = "daily_report"
STUB_MESSAGE = "Coordinator stub accepted the daily report job."
STUB_WARNING = AgentWarning(
    code="stub_mode",
    message="Real LangGraph orchestration is not implemented yet.",
)

logger = logging.getLogger(__name__)

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}


def _log_request_context(
    *,
    report_run_id: UUID,
    tenant_id: UUID,
    store_id: UUID,
    authorization: str | None,
    request_id: str | None,
) -> None:
    auth_present = bool(authorization)
    auth_scheme = None
    if authorization:
        scheme = authorization.split(" ", 1)[0]
        auth_scheme = scheme if scheme else None

    logger.info(
        "Daily report stub request received",
        extra={
            "report_run_id": str(report_run_id),
            "tenant_id": str(tenant_id),
            "store_id": str(store_id),
            "auth_present": auth_present,
            "auth_scheme": auth_scheme,
            "request_id": request_id,
        },
    )


@app.post("/workflows/daily-report", response_model=DailyReportStubResponse)
def trigger_daily_report_stub(
    payload: DailyReportJobRequest,
    authorization: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> DailyReportStubResponse:
    """Accept a daily report job from Django/Celery without running real orchestration."""
    _log_request_context(
        report_run_id=payload.report_run_id,
        tenant_id=payload.tenant_id,
        store_id=payload.store_id,
        authorization=authorization,
        request_id=x_request_id or payload.request_id,
    )

    if authorization is not None and not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use Bearer scheme.",
        )

    return DailyReportStubResponse(
        status="accepted",
        workflow=WORKFLOW_DAILY_REPORT,
        report_run_id=str(payload.report_run_id),
        message=STUB_MESSAGE,
        warnings=[STUB_WARNING],
    )
