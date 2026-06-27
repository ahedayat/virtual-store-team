from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from accounts.constants import AI_SERVICE_COORDINATOR
from accounts.service_jwt import mint_service_jwt
from operations.models import ReportRun

logger = logging.getLogger(__name__)

COORDINATOR_WORKFLOW_COMPLETED = "completed"
COORDINATOR_WORKFLOW_FAILED = "failed"
LEGACY_STUB_STATUS = "accepted"


@dataclass(frozen=True)
class CoordinatorDailyReportResult:
    http_status_code: int
    workflow_status: str
    report_run_id: str
    message: str


class CoordinatorClientError(Exception):
    """Raised when the coordinator daily report HTTP call fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class CoordinatorDailyReportClient:
    @classmethod
    def build_payload(cls, *, report_run: ReportRun) -> dict[str, str | dict[str, str]]:
        report_run_id = str(report_run.id)
        return {
            "report_run_id": report_run_id,
            "tenant_id": str(report_run.tenant_id),
            "store_id": str(report_run.store_id),
            "context_ref": {
                "type": "report_run",
                "id": report_run_id,
            },
        }

    @classmethod
    def build_auth_headers(cls, *, report_run: ReportRun) -> dict[str, str]:
        token = mint_service_jwt(
            service_name=AI_SERVICE_COORDINATOR,
            tenant_id=report_run.tenant_id,
            store_id=report_run.store_id,
            report_run_id=report_run.id,
        )
        return {"Authorization": f"Bearer {token}"}

    @classmethod
    def parse_response_body(
        cls,
        *,
        report_run: ReportRun,
        status_code: int,
        raw_body: bytes,
    ) -> CoordinatorDailyReportResult:
        if not raw_body:
            raise CoordinatorClientError(
                "Coordinator returned an empty response body.",
                status_code=status_code,
                error_class="EmptyResponse",
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoordinatorClientError(
                "Coordinator returned an invalid JSON response.",
                status_code=status_code,
                error_class=exc.__class__.__name__,
            ) from exc

        if not isinstance(payload, dict):
            raise CoordinatorClientError(
                "Coordinator response must be a JSON object.",
                status_code=status_code,
                error_class="InvalidResponse",
            )

        workflow_status = payload.get("status")
        if workflow_status == LEGACY_STUB_STATUS:
            raise CoordinatorClientError(
                "Coordinator returned a stub acceptance response without completing the workflow.",
                status_code=status_code,
                error_class="StubResponse",
            )

        if workflow_status not in {COORDINATOR_WORKFLOW_COMPLETED, COORDINATOR_WORKFLOW_FAILED}:
            raise CoordinatorClientError(
                "Coordinator returned an unsupported workflow status.",
                status_code=status_code,
                error_class="InvalidWorkflowStatus",
            )

        report_run_id = payload.get("report_run_id")
        if report_run_id is None:
            raise CoordinatorClientError(
                "Coordinator response is missing report_run_id.",
                status_code=status_code,
                error_class="InvalidResponse",
            )

        if str(report_run_id) != str(report_run.id):
            raise CoordinatorClientError(
                "Coordinator response report_run_id does not match the requested run.",
                status_code=status_code,
                error_class="ReportRunMismatch",
            )

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            message = (
                "Daily report workflow completed."
                if workflow_status == COORDINATOR_WORKFLOW_COMPLETED
                else "Daily report workflow failed."
            )

        return CoordinatorDailyReportResult(
            http_status_code=status_code,
            workflow_status=str(workflow_status),
            report_run_id=str(report_run_id),
            message=message.strip(),
        )

    @classmethod
    def trigger_daily_report(cls, *, report_run: ReportRun) -> CoordinatorDailyReportResult:
        url = settings.COORDINATOR_DAILY_REPORT_URL
        payload = cls.build_payload(report_run=report_run)
        headers = {
            "Content-Type": "application/json",
            **cls.build_auth_headers(report_run=report_run),
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout = settings.COORDINATOR_HTTP_TIMEOUT_SECONDS

        try:
            with urlopen(request, timeout=timeout) as response:
                status_code = response.status
                raw_body = response.read()
        except HTTPError as exc:
            raise CoordinatorClientError(
                f"Coordinator returned HTTP {exc.code}.",
                status_code=exc.code,
                error_class=exc.__class__.__name__,
            ) from exc
        except (URLError, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise CoordinatorClientError(
                f"Coordinator request failed: {reason}.",
                error_class=exc.__class__.__name__,
            ) from exc

        if status_code < 200 or status_code >= 300:
            raise CoordinatorClientError(
                f"Coordinator returned HTTP {status_code}.",
                status_code=status_code,
                error_class="HTTPResponse",
            )

        result = cls.parse_response_body(
            report_run=report_run,
            status_code=status_code,
            raw_body=raw_body,
        )

        logger.info(
            "Coordinator daily report workflow finished",
            extra={
                "report_run_id": str(report_run.id),
                "tenant_id": str(report_run.tenant_id),
                "store_id": str(report_run.store_id),
                "http_status_code": status_code,
                "workflow_status": result.workflow_status,
            },
        )
        return result
