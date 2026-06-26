from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from accounts.constants import AI_SERVICE_COORDINATOR
from accounts.service_jwt import mint_service_jwt
from operations.models import ReportRun

logger = logging.getLogger(__name__)


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
    def trigger_daily_report(cls, *, report_run: ReportRun) -> int:
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

        logger.info(
            "Coordinator daily report request accepted",
            extra={
                "report_run_id": str(report_run.id),
                "tenant_id": str(report_run.tenant_id),
                "store_id": str(report_run.store_id),
                "http_status_code": status_code,
            },
        )
        return status_code
