from __future__ import annotations

import logging
import time

from celery import shared_task

from operations.coordinator_client import CoordinatorClientError, CoordinatorDailyReportClient
from operations.models import ReportRun
from operations.services import ReportRunService

logger = logging.getLogger(__name__)


@shared_task(name="reports.generate_daily")
def generate_daily(report_run_id: str) -> dict[str, str]:
    """Run the daily report lifecycle: running → coordinator HTTP → completed/failed."""
    try:
        report_run = ReportRun.objects.select_related("tenant", "store").get(pk=report_run_id)
    except ReportRun.DoesNotExist:
        logger.error(
            "ReportRun not found for daily report task",
            extra={"report_run_id": report_run_id},
        )
        return {"status": "skipped", "reason": "report_run_not_found"}

    log_context = {
        "report_run_id": str(report_run.id),
        "tenant_id": str(report_run.tenant_id),
        "store_id": str(report_run.store_id),
    }

    if ReportRunService.is_terminal(report_run):
        logger.info(
            "Skipping daily report task for terminal ReportRun",
            extra={**log_context, "report_run_status": report_run.status},
        )
        return {"status": "skipped", "reason": "terminal_status"}

    report_run = ReportRunService.mark_running(report_run=report_run)
    report_run.refresh_from_db()

    started_at = time.monotonic()
    try:
        status_code = CoordinatorDailyReportClient.trigger_daily_report(report_run=report_run)
    except CoordinatorClientError as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.warning(
            "Coordinator daily report request failed",
            extra={
                **log_context,
                "duration_ms": duration_ms,
                "http_status_code": exc.status_code,
                "error_class": exc.error_class,
            },
        )
        ReportRunService.mark_failed(report_run=report_run, error_message=str(exc))
        return {"status": "failed", "report_run_id": str(report_run.id)}

    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "Coordinator daily report request succeeded",
        extra={
            **log_context,
            "duration_ms": duration_ms,
            "http_status_code": status_code,
        },
    )

    report_run.refresh_from_db()
    if not ReportRunService.is_terminal(report_run):
        ReportRunService.mark_completed_if_still_running(report_run=report_run)

    report_run.refresh_from_db()
    return {
        "status": report_run.status,
        "report_run_id": str(report_run.id),
    }
