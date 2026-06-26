from unittest.mock import patch

from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from operations.constants import (
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.models import ReportRun
from operations.services import ReportRunService
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


@override_settings(**TEST_JWT_SETTINGS, CELERY_TASK_ALWAYS_EAGER=True)
class ReportGenerateAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.other_store = Store.objects.create(
            tenant=self.tenant,
            name="Store B",
            slug="store-b",
            currency="USD",
        )
        self.other_tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.other_tenant_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Other Tenant Store",
            slug="other-store",
            currency="USD",
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="secure-pass-123",
            full_name="Manager Name",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        self.other_store_manager = User.objects.create_user(
            email="manager-b@example.com",
            password="secure-pass-123",
            full_name="Manager B",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.other_store,
        )
        self.other_tenant_manager = User.objects.create_user(
            email="other-tenant@example.com",
            password="secure-pass-123",
            full_name="Other Tenant Manager",
            role=UserRole.MANAGER,
            tenant=self.other_tenant,
            store=self.other_tenant_store,
        )
        self.tenant_manager = User.objects.create_user(
            email="tenant-manager@example.com",
            password="secure-pass-123",
            full_name="Tenant Manager",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=None,
        )
        self.generate_url = reverse("api-reports-generate")

    @patch.object(generate_daily, "delay")
    def test_creates_queued_report_run_and_enqueues_task(self, mock_delay):
        mock_delay.return_value.id = "celery-task-123"
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], REPORT_RUN_STATUS_QUEUED)
        self.assertEqual(response.data["task_id"], "celery-task-123")

        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.tenant_id, self.tenant.id)
        self.assertEqual(report_run.store_id, self.store.id)
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_QUEUED)
        mock_delay.assert_called_once_with(str(report_run.id))

    @patch.object(generate_daily, "delay")
    def test_duplicate_request_while_queued_returns_409(self, mock_delay):
        mock_delay.return_value.id = "celery-task-123"
        self.client.force_authenticate(user=self.manager)

        first = self.client.post(self.generate_url)
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        mock_delay.assert_called_once()

        second = self.client.post(self.generate_url)

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            second.data["detail"],
            "An active report run already exists for this store.",
        )
        self.assertEqual(second.data["existing_report_run_id"], first.data["report_run_id"])
        self.assertEqual(second.data["status"], REPORT_RUN_STATUS_QUEUED)
        self.assertIn("created_at", second.data)
        self.assertEqual(ReportRun.objects.filter(tenant=self.tenant, store=self.store).count(), 1)
        mock_delay.assert_called_once()

    @patch.object(generate_daily, "delay")
    def test_duplicate_request_while_running_returns_409(self, mock_delay):
        mock_delay.return_value.id = "celery-task-123"
        self.client.force_authenticate(user=self.manager)

        first = self.client.post(self.generate_url)
        report_run = ReportRun.objects.get(pk=first.data["report_run_id"])
        report_run.status = REPORT_RUN_STATUS_RUNNING
        report_run.save(update_fields=["status", "updated_at"])

        second = self.client.post(self.generate_url)

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["existing_report_run_id"], str(report_run.id))
        self.assertEqual(second.data["status"], REPORT_RUN_STATUS_RUNNING)
        mock_delay.assert_called_once()

    @patch.object(generate_daily, "delay")
    def test_new_request_after_completed_creates_run(self, mock_delay):
        mock_delay.return_value.id = "celery-task-123"
        self.client.force_authenticate(user=self.manager)

        first = self.client.post(self.generate_url)
        report_run = ReportRun.objects.get(pk=first.data["report_run_id"])
        report_run.status = REPORT_RUN_STATUS_COMPLETED
        report_run.save(update_fields=["status", "updated_at"])
        mock_delay.reset_mock()
        mock_delay.return_value.id = "celery-task-456"

        second = self.client.post(self.generate_url)

        self.assertEqual(second.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotEqual(second.data["report_run_id"], str(report_run.id))
        self.assertEqual(
            ReportRun.objects.filter(tenant=self.tenant, store=self.store).count(),
            2,
        )
        mock_delay.assert_called_once_with(second.data["report_run_id"])

    @patch.object(generate_daily, "delay")
    def test_new_request_after_failed_creates_run(self, mock_delay):
        mock_delay.return_value.id = "celery-task-123"
        self.client.force_authenticate(user=self.manager)

        first = self.client.post(self.generate_url)
        report_run = ReportRun.objects.get(pk=first.data["report_run_id"])
        report_run.status = REPORT_RUN_STATUS_FAILED
        report_run.error_message = "Coordinator unavailable"
        report_run.save(update_fields=["status", "error_message", "updated_at"])
        mock_delay.reset_mock()
        mock_delay.return_value.id = "celery-task-789"

        second = self.client.post(self.generate_url)

        self.assertEqual(second.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotEqual(second.data["report_run_id"], str(report_run.id))
        mock_delay.assert_called_once_with(second.data["report_run_id"])

    @patch.object(generate_daily, "delay")
    def test_different_stores_can_have_active_runs_independently(self, mock_delay):
        mock_delay.return_value.id = "celery-task-store-a"
        self.client.force_authenticate(user=self.manager)
        store_a_response = self.client.post(self.generate_url)
        self.assertEqual(store_a_response.status_code, status.HTTP_202_ACCEPTED)

        mock_delay.return_value.id = "celery-task-store-b"
        self.client.force_authenticate(user=self.other_store_manager)
        store_b_response = self.client.post(self.generate_url)

        self.assertEqual(store_b_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotEqual(
            store_a_response.data["report_run_id"],
            store_b_response.data["report_run_id"],
        )
        self.assertEqual(mock_delay.call_count, 2)

    @patch.object(generate_daily, "delay")
    def test_different_tenants_do_not_block_each_other(self, mock_delay):
        mock_delay.return_value.id = "celery-task-tenant-a"
        self.client.force_authenticate(user=self.manager)
        tenant_a_response = self.client.post(self.generate_url)
        self.assertEqual(tenant_a_response.status_code, status.HTTP_202_ACCEPTED)

        mock_delay.return_value.id = "celery-task-tenant-b"
        self.client.force_authenticate(user=self.other_tenant_manager)
        tenant_b_response = self.client.post(self.generate_url)

        self.assertEqual(tenant_b_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(mock_delay.call_count, 2)

    def test_requires_authentication(self):
        response = self.client.post(self.generate_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requires_store_scoped_user(self):
        self.client.force_authenticate(user=self.tenant_manager)

        response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("store", response.data["detail"].lower())


@override_settings(**TEST_JWT_SETTINGS)
class ReportRunDuplicatePreventionServiceTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )

    def test_create_queued_run_for_store_creates_first_run(self):
        result = ReportRunService.create_queued_run_for_store(
            tenant=self.tenant,
            store=self.store,
        )

        self.assertTrue(result.created)
        self.assertEqual(result.report_run.status, REPORT_RUN_STATUS_QUEUED)
        self.assertEqual(result.report_run.tenant_id, self.tenant.id)
        self.assertEqual(result.report_run.store_id, self.store.id)

    def test_create_queued_run_for_store_returns_existing_active_run(self):
        existing = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_RUNNING,
        )

        result = ReportRunService.create_queued_run_for_store(
            tenant=self.tenant,
            store=self.store,
        )

        self.assertFalse(result.created)
        self.assertEqual(result.report_run.id, existing.id)

    @patch.object(ReportRun.objects, "create")
    @patch.object(ReportRunService, "get_active_run_for_store")
    def test_create_queued_run_handles_integrity_error_race(
        self,
        mock_get_active,
        mock_create,
    ):
        existing = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_QUEUED,
        )
        mock_get_active.side_effect = [None, existing]
        mock_create.side_effect = IntegrityError("unique_active_report_run_per_store")

        result = ReportRunService.create_queued_run_for_store(
            tenant=self.tenant,
            store=self.store,
        )

        self.assertFalse(result.created)
        self.assertEqual(result.report_run.id, existing.id)

    def test_database_constraint_blocks_second_active_run(self):
        ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_QUEUED,
        )

        with self.assertRaises(IntegrityError):
            ReportRun.objects.create(
                tenant=self.tenant,
                store=self.store,
                status=REPORT_RUN_STATUS_RUNNING,
            )

    def test_database_constraint_allows_terminal_and_active_mix(self):
        ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_COMPLETED,
        )
        ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_FAILED,
        )

        active = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_QUEUED,
        )

        self.assertEqual(active.status, REPORT_RUN_STATUS_QUEUED)
