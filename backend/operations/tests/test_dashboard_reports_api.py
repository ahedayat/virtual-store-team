from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from operations.constants import (
    ACTION_TYPE_SALES_RESTOCK,
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
)
from operations.models import Action, DailyReport, ReportRun
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}


@override_settings(**TEST_JWT_SETTINGS)
class DashboardReportsAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.other_tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
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
        self.foreign_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Foreign Store",
            slug="foreign",
            currency="EUR",
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
        self.foreign_manager = User.objects.create_user(
            email="foreign@example.com",
            password="secure-pass-123",
            full_name="Foreign Manager",
            role=UserRole.MANAGER,
            tenant=self.other_tenant,
            store=self.foreign_store,
        )
        self.list_url = reverse("api-reports-list")
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)

    def _create_report_run(self, *, store=None, tenant=None, status_value=REPORT_RUN_STATUS_COMPLETED):
        store = store or self.store
        tenant = tenant or self.tenant
        report_run = ReportRun.objects.create(
            tenant=tenant,
            store=store,
            status=status_value,
        )
        if status_value == REPORT_RUN_STATUS_FAILED:
            report_run.error_message = "Coordinator timeout"
            report_run.save(update_fields=["error_message"])
        return report_run

    def _create_daily_report(self, report_run, **content_overrides):
        content = {
            "operational_insights": ["Revenue increased week over week."],
            "prioritized_actions": [{"action_id": "x", "priority": 1, "summary": "Restock"}],
            "content_suggestions": [],
            "support_insights": [],
            "next_steps": ["Review pending actions"],
            "period": {"from": "2026-06-19", "to": "2026-06-26"},
        }
        content.update(content_overrides)
        return DailyReport.objects.create(
            tenant=report_run.tenant,
            store=report_run.store,
            report_run=report_run,
            content=content,
            generated_at=timezone.now(),
        )

    def test_authenticated_list_access(self):
        report_run = self._create_report_run()
        self._create_daily_report(report_run)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["id"], str(report_run.id))
        self.assertEqual(item["status"], REPORT_RUN_STATUS_COMPLETED)
        self.assertIn("summary", item)
        self.assertIn("created_at", item)
        self.assertTrue(item["coordinator"]["has_daily_report"])

    def test_authenticated_detail_access(self):
        report_run = self._create_report_run()
        daily_report = self._create_daily_report(report_run)
        Action.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=report_run,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Restock",
            description="Low stock",
            payload={"sku": "BAG-001"},
            priority=1,
            requires_approval=True,
            status="pending_approval",
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-reports-detail", kwargs={"report_run_id": report_run.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(report_run.id))
        self.assertIsNotNone(response.data["daily_report"])
        self.assertEqual(response.data["daily_report"]["id"], str(daily_report.id))
        self.assertEqual(response.data["counts"]["actions"], 1)
        self.assertIn("sections", response.data["daily_report"])

    def test_list_ordered_newest_first(self):
        older = self._create_report_run()
        ReportRun.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        newer = self._create_report_run(status_value=REPORT_RUN_STATUS_QUEUED)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids[0], str(newer.id))
        self.assertEqual(ids[1], str(older.id))

    def test_store_isolation_on_list(self):
        self._create_report_run(store=self.store)
        self._create_report_run(store=self.other_store)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["store_id"], str(self.store.id))

    def test_cross_tenant_detail_returns_404(self):
        foreign_run = self._create_report_run(store=self.foreign_store, tenant=self.other_tenant)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-reports-detail", kwargs={"report_run_id": foreign_run.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_store_detail_returns_404_for_store_scoped_user(self):
        other_run = self._create_report_run(store=self.other_store)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-reports-detail", kwargs={"report_run_id": other_run.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_list_is_rejected(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_detail_is_rejected(self):
        report_run = self._create_report_run()
        response = self.client.get(
            reverse("api-reports-detail", kwargs={"report_run_id": report_run.id})
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_service_jwt_cannot_access_reports_list(self):
        token = mint_service_jwt(
            service_name=AI_SERVICE_SALES,
            tenant_id=self.tenant_id,
            store_id=self.store_id,
        )

        response = self.client.get(
            self.list_url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_failed_report_includes_error_message(self):
        report_run = self._create_report_run(status_value=REPORT_RUN_STATUS_FAILED)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-reports-detail", kwargs={"report_run_id": report_run.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["error_message"], "Coordinator timeout")

    def test_pagination_metadata(self):
        for index in range(3):
            report_run = self._create_report_run(status_value=REPORT_RUN_STATUS_COMPLETED)
            ReportRun.objects.filter(pk=report_run.pk).update(
                created_at=timezone.now() - timedelta(days=index)
            )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url, {"limit": 2, "offset": 0})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
