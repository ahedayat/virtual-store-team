from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR
from accounts.models import User, UserRole
from accounts.service_jwt import decode_service_jwt
from operations.constants import (
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.models import ReportRun
from operations.tests.mock_coordinator_server import MockCoordinatorServer
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
    "COORDINATOR_DAILY_REPORT_PATH": "/workflows/daily-report",
    "COORDINATOR_HTTP_TIMEOUT_SECONDS": 30,
}

EAGER_CELERY_SETTINGS = {
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_TASK_EAGER_PROPAGATES": True,
}


class CoordinatorIntegrationTests(APITestCase):
    """End-to-end report generation flow against a mock coordinator HTTP server."""

    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
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
        self.generate_url = reverse("api-reports-generate")
        self.mock_coordinator = MockCoordinatorServer()
        self.mock_coordinator.start()

    def tearDown(self):
        self.mock_coordinator.response_delay_seconds = 0.0
        self.mock_coordinator.stop()

    def _integration_settings(self, **overrides):
        settings = {
            **TEST_JWT_SETTINGS,
            **EAGER_CELERY_SETTINGS,
            "COORDINATOR_AGENT_URL": self.mock_coordinator.base_url,
            "COORDINATOR_DAILY_REPORT_URL": self.mock_coordinator.daily_report_url,
        }
        settings.update(overrides)
        return override_settings(**settings)

    def _assert_expected_coordinator_payload(self, report_run: ReportRun) -> None:
        self.assertEqual(len(self.mock_coordinator.requests), 1)
        request = self.mock_coordinator.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/workflows/daily-report")

        import json

        payload = json.loads(request["body"])
        report_run_id = str(report_run.id)
        self.assertEqual(payload["report_run_id"], report_run_id)
        self.assertEqual(payload["tenant_id"], str(self.tenant.id))
        self.assertEqual(payload["store_id"], str(self.store.id))
        self.assertEqual(
            payload["context_ref"],
            {"type": "report_run", "id": report_run_id},
        )

        auth_header = request["headers"].get("Authorization", "")
        self.assertTrue(auth_header.startswith("Bearer "))
        token = auth_header.removeprefix("Bearer ").strip()
        with self._integration_settings():
            claims = decode_service_jwt(token)
        self.assertEqual(claims["sub"], AI_SERVICE_COORDINATOR)
        self.assertEqual(str(claims["tenant_id"]), str(self.tenant.id))
        self.assertEqual(str(claims["store_id"]), str(self.store.id))
        self.assertEqual(str(claims["report_run_id"]), report_run_id)

    def test_success_path_completes_report_run_via_mock_coordinator(self):
        with self._integration_settings():
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], REPORT_RUN_STATUS_QUEUED)

        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)
        self.assertEqual(report_run.error_message, "")
        self._assert_expected_coordinator_payload(report_run)

    def test_coordinator_http_500_marks_report_run_failed_with_safe_error(self):
        self.mock_coordinator.set_json_response(
            {
                "error": "internal failure",
                "customer_email": "customer@example.com",
                "customer_phone": "+98-912-345-6789",
            },
            status=500,
        )
        with self._integration_settings():
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("500", report_run.error_message)
        self.assertNotIn("customer@example.com", report_run.error_message)
        self.assertNotIn("+98-912-345-6789", report_run.error_message)
        self.assertNotIn("customer_email", report_run.error_message)
        self._assert_expected_coordinator_payload(report_run)

    def test_coordinator_connection_error_marks_report_run_failed(self):
        unreachable_url = "http://127.0.0.1:1/workflows/daily-report"
        with self._integration_settings(
            COORDINATOR_AGENT_URL="http://127.0.0.1:1",
            COORDINATOR_DAILY_REPORT_URL=unreachable_url,
        ):
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertTrue(report_run.error_message)
        self.assertNotIn("@", report_run.error_message)

    def test_coordinator_timeout_marks_report_run_failed(self):
        self.mock_coordinator.response_delay_seconds = 2.0
        with self._integration_settings(COORDINATOR_HTTP_TIMEOUT_SECONDS=1):
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertIn("timed out", report_run.error_message.lower())

    def test_duplicate_active_run_does_not_call_coordinator(self):
        existing = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_QUEUED,
        )
        with self._integration_settings():
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["existing_report_run_id"], str(existing.id))
        self.assertEqual(response.data["status"], REPORT_RUN_STATUS_QUEUED)
        self.assertEqual(len(self.mock_coordinator.requests), 0)
        self.assertEqual(ReportRun.objects.filter(tenant=self.tenant, store=self.store).count(), 1)

    def test_duplicate_running_run_does_not_call_coordinator(self):
        existing = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_RUNNING,
        )
        with self._integration_settings():
            self.client.force_authenticate(user=self.manager)
            response = self.client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["existing_report_run_id"], str(existing.id))
        self.assertEqual(response.data["status"], REPORT_RUN_STATUS_RUNNING)
        self.assertEqual(len(self.mock_coordinator.requests), 0)
