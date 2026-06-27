from __future__ import annotations

import logging
import time

from celery import shared_task
from django.core.exceptions import ValidationError

from operations.constants import (
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
)
from operations.coordinator_client import (
    COORDINATOR_WORKFLOW_COMPLETED,
    COORDINATOR_WORKFLOW_FAILED,
    CoordinatorClientError,
    CoordinatorDailyReportClient,
)
from operations.models import Action, ReportRun
from operations.services import ActionService, ReportRunService

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
        coordinator_result = CoordinatorDailyReportClient.trigger_daily_report(
            report_run=report_run
        )
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
        "Coordinator daily report workflow returned",
        extra={
            **log_context,
            "duration_ms": duration_ms,
            "http_status_code": coordinator_result.http_status_code,
            "workflow_status": coordinator_result.workflow_status,
        },
    )

    report_run.refresh_from_db()
    if coordinator_result.workflow_status == COORDINATOR_WORKFLOW_COMPLETED:
        if report_run.status == REPORT_RUN_STATUS_COMPLETED:
            return {
                "status": report_run.status,
                "report_run_id": str(report_run.id),
            }
        ReportRunService.mark_failed(
            report_run=report_run,
            error_message=(
                "Coordinator reported completion but the report run was not completed in Django."
            ),
        )
        report_run.refresh_from_db()
        return {
            "status": report_run.status,
            "report_run_id": str(report_run.id),
        }

    if coordinator_result.workflow_status == COORDINATOR_WORKFLOW_FAILED:
        if report_run.status != REPORT_RUN_STATUS_FAILED:
            ReportRunService.mark_failed(
                report_run=report_run,
                error_message=coordinator_result.message,
            )
        report_run.refresh_from_db()
        return {
            "status": report_run.status,
            "report_run_id": str(report_run.id),
        }

    ReportRunService.mark_failed(
        report_run=report_run,
        error_message="Coordinator returned an unsupported workflow completion status.",
    )
    report_run.refresh_from_db()
    return {
        "status": report_run.status,
        "report_run_id": str(report_run.id),
    }


@shared_task(name="actions.execute")
def execute_action(action_id: str) -> dict[str, str | dict[str, str]]:
    """Execute a queued action using the MVP stub handler (no external side effects)."""
    try:
        action = Action.objects.select_related("tenant", "store").get(pk=action_id)
    except (Action.DoesNotExist, ValidationError):
        logger.error(
            "Action not found for execute task",
            extra={"action_id": action_id},
        )
        return {"status": "skipped", "reason": "action_not_found"}

    log_context = {
        "action_id": str(action.id),
        "tenant_id": str(action.tenant_id),
        "store_id": str(action.store_id),
        "action_type": action.action_type,
        "action_status": action.status,
    }

    result = ActionService.execute_stub(action=action)
    outcome = result["outcome"]

    if outcome == "executed":
        logger.info(
            "Action stub execution completed",
            extra={**log_context, "execution_outcome": outcome},
        )
        return {
            "status": "executed",
            "action_id": result["action_id"],
            "execution_result": result["execution_result"],
        }

    logger.info(
        "Action execute task skipped",
        extra={**log_context, "execution_outcome": outcome, "result_status": result.get("status")},
    )
    return {
        "status": "skipped",
        "reason": outcome,
        "action_id": result["action_id"],
        "action_status": result.get("status", action.status),
    }


@shared_task(name="maintenance.cleanup_stale_report_runs")
def cleanup_stale_report_runs() -> dict[str, int | list[str]]:
    """Mark active report runs that exceeded the stale timeout as failed."""
    result = ReportRunService.cleanup_stale_active_runs()
    logger.info(
        "Stale report run cleanup completed",
        extra={
            "marked_failed_count": result["marked_failed_count"],
            "stale_timeout_seconds": result["stale_timeout_seconds"],
        },
    )
    return result
