from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import TestCase, override_settings

from operations.constants import (
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.coordinator_client import (
    COORDINATOR_WORKFLOW_COMPLETED,
    COORDINATOR_WORKFLOW_FAILED,
    CoordinatorClientError,
    CoordinatorDailyReportClient,
    CoordinatorDailyReportResult,
)
from operations.models import ReportRun
from operations.tasks import generate_daily
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
    "COORDINATOR_AGENT_URL": "http://coordinator-agent:8100",
    "COORDINATOR_DAILY_REPORT_PATH": "/workflows/daily-report",
    "COORDINATOR_DAILY_REPORT_URL": "http://coordinator-agent:8100/workflows/daily-report",
    "COORDINATOR_HTTP_TIMEOUT_SECONDS": 30,
}


@override_settings(**TEST_JWT_SETTINGS)
class GenerateDailyTaskTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )

    def _create_report_run(self, *, status=REPORT_RUN_STATUS_QUEUED) -> ReportRun:
        return ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=status,
        )

    def _completed_result(self, report_run: ReportRun) -> CoordinatorDailyReportResult:
        return CoordinatorDailyReportResult(
            http_status_code=200,
            workflow_status=COORDINATOR_WORKFLOW_COMPLETED,
            report_run_id=str(report_run.id),
            message="Daily report workflow completed.",
        )

    def _failed_result(self, report_run: ReportRun) -> CoordinatorDailyReportResult:
        return CoordinatorDailyReportResult(
            http_status_code=200,
            workflow_status=COORDINATOR_WORKFLOW_FAILED,
            report_run_id=str(report_run.id),
            message="Context fetch timed out.",
        )

    def test_marks_queued_report_run_running_before_coordinator_call(self):
        report_run = self._create_report_run()
        observed_statuses: list[str] = []

        def capture_running_state(*, report_run: ReportRun) -> CoordinatorDailyReportResult:
            observed_statuses.append(report_run.status)
            ReportRun.objects.filter(pk=report_run.pk).update(
                status=REPORT_RUN_STATUS_COMPLETED
            )
            return self._completed_result(report_run)

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=capture_running_state,
        ):
            generate_daily(str(report_run.id))

        self.assertEqual(observed_statuses, [REPORT_RUN_STATUS_RUNNING])
        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)

    def test_marks_report_run_completed_when_coordinator_and_django_are_completed(self):
        report_run = self._create_report_run()

        def complete_via_internal_api(*, report_run: ReportRun) -> CoordinatorDailyReportResult:
            ReportRun.objects.filter(pk=report_run.pk).update(
                status=REPORT_RUN_STATUS_COMPLETED
            )
            return self._completed_result(report_run)

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=complete_via_internal_api,
        ):
            result = generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)
        self.assertEqual(report_run.error_message, "")
        self.assertEqual(result["status"], REPORT_RUN_STATUS_COMPLETED)

    def test_does_not_mark_completed_when_coordinator_returns_stub_accepted(self):
        report_run = self._create_report_run()

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=CoordinatorClientError(
                "Coordinator returned a stub acceptance response without completing the workflow.",
                status_code=200,
                error_class="StubResponse",
            ),
        ):
            result = generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("stub acceptance", report_run.error_message.lower())
        self.assertEqual(result["status"], "failed")

    def test_marks_report_run_failed_when_coordinator_reports_completed_without_django(self):
        report_run = self._create_report_run()

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            return_value=self._completed_result(report_run),
        ):
            result = generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("not completed in Django", report_run.error_message)
        self.assertEqual(result["status"], REPORT_RUN_STATUS_FAILED)

    def test_marks_report_run_failed_when_coordinator_workflow_fails(self):
        report_run = self._create_report_run()

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            return_value=self._failed_result(report_run),
        ):
            result = generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("timed out", report_run.error_message)
        self.assertEqual(result["status"], REPORT_RUN_STATUS_FAILED)

    def test_marks_report_run_failed_when_coordinator_returns_non_2xx(self):
        report_run = self._create_report_run()

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=CoordinatorClientError(
                "Coordinator returned HTTP 502.",
                status_code=502,
                error_class="HTTPError",
            ),
        ):
            result = generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("502", report_run.error_message)
        self.assertEqual(result["status"], "failed")

    def test_marks_report_run_failed_on_connection_error(self):
        report_run = self._create_report_run()

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=CoordinatorClientError(
                "Coordinator request failed: Connection refused.",
                error_class="URLError",
            ),
        ):
            generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("Connection refused", report_run.error_message)

    def test_skips_terminal_completed_report_run(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_COMPLETED)

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
        ) as mock_trigger:
            result = generate_daily(str(report_run.id))

        mock_trigger.assert_not_called()
        self.assertEqual(result["reason"], "terminal_status")

    def test_skips_terminal_failed_report_run(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_FAILED)

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
        ) as mock_trigger:
            result = generate_daily(str(report_run.id))

        mock_trigger.assert_not_called()
        self.assertEqual(result["reason"], "terminal_status")

    def test_does_not_overwrite_completed_when_internal_api_already_completed(self):
        report_run = self._create_report_run()

        def complete_via_internal_api(*, report_run: ReportRun) -> CoordinatorDailyReportResult:
            ReportRun.objects.filter(pk=report_run.pk).update(
                status=REPORT_RUN_STATUS_COMPLETED
            )
            return self._completed_result(report_run)

        with patch.object(
            CoordinatorDailyReportClient,
            "trigger_daily_report",
            side_effect=complete_via_internal_api,
        ):
            generate_daily(str(report_run.id))

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)

    @patch("operations.coordinator_client.urlopen")
    def test_coordinator_client_maps_http_error(self, mock_urlopen):
        report_run = self._create_report_run()
        mock_urlopen.side_effect = HTTPError(
            "http://coordinator-agent:8100/workflows/daily-report",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )

        with self.assertRaises(CoordinatorClientError) as exc_info:
            CoordinatorDailyReportClient.trigger_daily_report(report_run=report_run)

        self.assertEqual(exc_info.exception.status_code, 503)

    @patch("operations.coordinator_client.urlopen")
    def test_coordinator_client_maps_url_error(self, mock_urlopen):
        report_run = self._create_report_run()
        mock_urlopen.side_effect = URLError("timed out")

        with self.assertRaises(CoordinatorClientError) as exc_info:
            CoordinatorDailyReportClient.trigger_daily_report(report_run=report_run)

        self.assertEqual(exc_info.exception.error_class, "URLError")

    @patch("operations.coordinator_client.urlopen")
    def test_coordinator_client_rejects_legacy_stub_response(self, mock_urlopen):
        import json

        report_run = self._create_report_run()
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {
                "status": "accepted",
                "report_run_id": str(report_run.id),
                "message": "stub",
            }
        ).encode("utf-8")

        with self.assertRaises(CoordinatorClientError) as exc_info:
            CoordinatorDailyReportClient.trigger_daily_report(report_run=report_run)

        self.assertEqual(exc_info.exception.error_class, "StubResponse")

    @patch("operations.coordinator_client.urlopen")
    def test_coordinator_client_parses_completed_response(self, mock_urlopen):
        report_run = self._create_report_run()
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.status = 200
        mock_response.read.return_value = (
            b'{"status":"completed","workflow":"daily_report","report_run_id":"'
            + str(report_run.id).encode()
            + b'","message":"Daily report workflow completed."}'
        )

        result = CoordinatorDailyReportClient.trigger_daily_report(report_run=report_run)

        self.assertEqual(result.workflow_status, COORDINATOR_WORKFLOW_COMPLETED)
        self.assertEqual(result.report_run_id, str(report_run.id))
