from datetime import timedelta

from config.celery import app as celery_app
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from operations.constants import (
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.models import ReportRun
from operations.services import ReportRunService
from operations.tasks import cleanup_stale_report_runs
from stores.models import Store
from tenants.models import Tenant


class CleanupStaleReportRunsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )

    def _create_report_run(self, *, status: str) -> ReportRun:
        return ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=status,
        )

    def _age_report_run(self, report_run: ReportRun, *, seconds: int) -> None:
        aged_at = timezone.now() - timedelta(seconds=seconds)
        ReportRun.objects.filter(pk=report_run.pk).update(updated_at=aged_at)
        report_run.refresh_from_db()

    @override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=600)
    def test_stale_queued_report_run_is_marked_failed(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_QUEUED)
        self._age_report_run(report_run, seconds=700)

        result = cleanup_stale_report_runs()

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("stale-run cleanup", report_run.error_message)
        self.assertIn("600s", report_run.error_message)
        self.assertEqual(result["marked_failed_count"], 1)
        self.assertEqual(result["marked_failed_ids"], [str(report_run.id)])

    @override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=600)
    def test_stale_running_report_run_is_marked_failed(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_RUNNING)
        self._age_report_run(report_run, seconds=700)

        result = cleanup_stale_report_runs()

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertEqual(result["marked_failed_count"], 1)

    @override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=600)
    def test_fresh_active_report_run_is_not_modified(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_RUNNING)

        result = cleanup_stale_report_runs()

        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_RUNNING)
        self.assertEqual(report_run.error_message, "")
        self.assertEqual(result["marked_failed_count"], 0)
        self.assertEqual(result["marked_failed_ids"], [])

    @override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=600)
    def test_terminal_report_run_is_not_modified(self):
        completed = self._create_report_run(status=REPORT_RUN_STATUS_COMPLETED)
        failed = self._create_report_run(status=REPORT_RUN_STATUS_FAILED)
        self._age_report_run(completed, seconds=700)
        self._age_report_run(failed, seconds=700)
        failed.error_message = "Original failure."
        failed.save(update_fields=["error_message", "updated_at"])

        result = cleanup_stale_report_runs()

        completed.refresh_from_db()
        failed.refresh_from_db()
        self.assertEqual(completed.status, REPORT_RUN_STATUS_COMPLETED)
        self.assertEqual(failed.status, REPORT_RUN_STATUS_FAILED)
        self.assertEqual(failed.error_message, "Original failure.")
        self.assertEqual(result["marked_failed_count"], 0)

    @override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=600)
    def test_cleanup_is_idempotent_for_already_failed_stale_runs(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_FAILED)
        self._age_report_run(report_run, seconds=700)
        report_run.error_message = "Already failed."
        report_run.save(update_fields=["error_message", "updated_at"])

        result = cleanup_stale_report_runs()

        report_run.refresh_from_db()
        self.assertEqual(report_run.error_message, "Already failed.")
        self.assertEqual(result["marked_failed_count"], 0)

    def test_service_returns_useful_count_and_timeout(self):
        report_run = self._create_report_run(status=REPORT_RUN_STATUS_QUEUED)
        self._age_report_run(report_run, seconds=700)

        with override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=120):
            result = ReportRunService.cleanup_stale_active_runs()

        self.assertEqual(result["marked_failed_count"], 1)
        self.assertEqual(result["stale_timeout_seconds"], 120)
        self.assertIn(str(report_run.id), result["marked_failed_ids"])

    def test_celery_beat_schedule_contains_stale_report_cleanup(self):
        schedule = settings.CELERY_BEAT_SCHEDULE
        self.assertIn("maintenance-cleanup-stale-report-runs", schedule)
        self.assertEqual(
            schedule["maintenance-cleanup-stale-report-runs"]["task"],
            "maintenance.cleanup_stale_report_runs",
        )

    def test_task_is_registered_with_canonical_name(self):
        self.assertIn("maintenance.cleanup_stale_report_runs", celery_app.tasks)
        self.assertEqual(
            celery_app.tasks["maintenance.cleanup_stale_report_runs"].name,
            "maintenance.cleanup_stale_report_runs",
        )
