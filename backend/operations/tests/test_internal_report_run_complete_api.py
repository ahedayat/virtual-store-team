from unittest.mock import patch

import jwt
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR, AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from operations.constants import (
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_TYPE_SALES_RESTOCK,
    REPORT_RUN_ACTIVE_STATUSES,
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.models import Action, AgentOutput, DailyReport, ReportRun
from operations.services import ActionService, ReportRunService
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}


@override_settings(**TEST_JWT_SETTINGS)
class InternalReportRunCompleteAPITests(APITestCase):
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
        self.report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_RUNNING,
        )
        self.other_report_run = ReportRun.objects.create(
            tenant=self.other_tenant,
            store=self.foreign_store,
            status=REPORT_RUN_STATUS_RUNNING,
        )
        self.other_store_report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.other_store,
            status=REPORT_RUN_STATUS_RUNNING,
        )
        self.failed_report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_FAILED,
            error_message="Coordinator timeout",
        )
        self.completed_report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_COMPLETED,
        )
        self.agent_output = AgentOutput.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=self.report_run,
            agent_name=AI_SERVICE_SALES,
            output={"output_type": "sales_analysis", "payload": {}},
        )
        self.foreign_agent_output = AgentOutput.objects.create(
            tenant=self.other_tenant,
            store=self.foreign_store,
            report_run=self.other_report_run,
            agent_name=AI_SERVICE_SALES,
            output={"output_type": "sales_analysis", "payload": {}},
        )
        self.action = Action.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=self.report_run,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Restock item",
            description="Low stock",
            payload={"sku": "BAG-001"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        self.foreign_action = Action.objects.create(
            tenant=self.other_tenant,
            store=self.foreign_store,
            report_run=self.other_report_run,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Foreign restock",
            description="Foreign low stock",
            payload={"sku": "BAG-999"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)

    def _complete_url(self, report_run_id):
        return reverse("internal-ai-report-runs-complete", kwargs={"report_run_id": report_run_id})

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_COORDINATOR),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _create_running_report_run_with_refs(self):
        ReportRun.objects.filter(
            tenant=self.tenant,
            store=self.store,
            status__in=REPORT_RUN_ACTIVE_STATUSES,
        ).update(status=REPORT_RUN_STATUS_COMPLETED)
        report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=REPORT_RUN_STATUS_RUNNING,
        )
        agent_output = AgentOutput.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=report_run,
            agent_name=AI_SERVICE_SALES,
            output={"output_type": "sales_analysis", "payload": {}},
        )
        action = Action.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=report_run,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Restock item",
            description="Low stock",
            payload={"sku": "BAG-001"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        return report_run, agent_output, action

    def _valid_completion_body(self, **overrides):
        report_run = overrides.pop("report_run", self.report_run)
        agent_output = overrides.pop("agent_output", self.agent_output)
        action = overrides.pop("action", self.action)
        body = {
            "report": {
                "generated_at": "2026-06-26T10:30:00Z",
                "period": {
                    "from": "2026-06-25T00:00:00Z",
                    "to": "2026-06-26T00:00:00Z",
                },
                "sales_summary": {
                    "total_revenue": 12500000,
                    "order_count": 18,
                    "top_products": [],
                    "low_performers": [],
                },
                "operational_insights": [
                    "Inventory is low for two fast-moving products."
                ],
                "prioritized_actions": [
                    {
                        "action_id": str(action.id),
                        "priority": 1,
                        "summary": "Restock the best-selling leather tote.",
                    }
                ],
                "content_suggestions": [
                    {
                        "type": "instagram_caption",
                        "draft_preview": "Summer collection preview.",
                    }
                ],
                "support_insights": [
                    {
                        "theme": "shipping questions",
                        "message_count": 4,
                        "summary": "Customers asked about delivery timing.",
                    }
                ],
                "next_steps": ["Review pending approval actions."],
                "warnings": [],
            },
            "agent_output_ids": [str(agent_output.id)],
            "action_ids": [str(action.id)],
            "metadata": {
                "coordinator_version": "mock",
                "duration_ms": 3500,
            },
        }
        body.update(overrides)
        return body

    def test_valid_coordinator_jwt_can_complete_running_report_run(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["report_run_id"]), str(report_run.id))
        self.assertEqual(response.data["status"], REPORT_RUN_STATUS_COMPLETED)
        self.assertIn("daily_report_id", response.data)
        self.assertIn("completed_at", response.data)

    def test_missing_token_is_rejected(self):
        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=self._valid_completion_body(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(DailyReport.objects.exists())

    def test_invalid_token_is_rejected(self):
        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=self._valid_completion_body(),
            format="json",
            HTTP_AUTHORIZATION="Bearer not-a-valid-jwt",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(DailyReport.objects.exists())

    def test_session_authenticated_user_cannot_complete_report_run(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=self._valid_completion_body(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(DailyReport.objects.exists())

    def test_non_coordinator_service_cannot_complete_report_run(self):
        token = self._mint_token(service_name=AI_SERVICE_SALES)

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.report_run.refresh_from_db()
        self.assertEqual(self.report_run.status, REPORT_RUN_STATUS_RUNNING)
        self.assertFalse(DailyReport.objects.exists())

    def test_cross_tenant_report_run_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(self.other_report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(DailyReport.objects.exists())

    def test_cross_store_report_run_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(self.other_store_report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(DailyReport.objects.exists())

    def test_valid_completion_creates_daily_report(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        daily_report = DailyReport.objects.get(id=response.data["daily_report_id"])
        self.assertEqual(daily_report.report_run_id, report_run.id)
        self.assertEqual(daily_report.tenant_id, self.tenant.id)
        self.assertEqual(daily_report.store_id, self.store.id)

    def test_valid_completion_changes_report_run_status_to_completed(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_run.refresh_from_db()
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)
        self.assertEqual(report_run.error_message, "")

    def test_valid_completion_stores_structured_report_payload(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        daily_report = DailyReport.objects.get(id=response.data["daily_report_id"])
        self.assertEqual(
            daily_report.content["sales_summary"]["order_count"],
            body["report"]["sales_summary"]["order_count"],
        )
        self.assertEqual(
            daily_report.content["metadata"]["coordinator_version"],
            "mock",
        )
        self.assertEqual(
            daily_report.content["operational_insights"],
            body["report"]["operational_insights"],
        )

    def test_completion_validates_agent_output_ids(self):
        token = self._mint_token()
        body = self._valid_completion_body(agent_output_ids=["00000000-0000-4000-8000-000000000099"])

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DailyReport.objects.exists())

    def test_cross_tenant_agent_output_ids_are_rejected(self):
        token = self._mint_token()
        body = self._valid_completion_body(
            agent_output_ids=[str(self.foreign_agent_output.id)],
            action_ids=[],
        )

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DailyReport.objects.exists())

    def test_completion_validates_action_ids(self):
        token = self._mint_token()
        body = self._valid_completion_body(action_ids=["00000000-0000-4000-8000-000000000099"])

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DailyReport.objects.exists())

    def test_cross_tenant_action_ids_are_rejected(self):
        token = self._mint_token()
        body = self._valid_completion_body(
            agent_output_ids=[],
            action_ids=[str(self.foreign_action.id)],
        )

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DailyReport.objects.exists())

    def test_failed_report_run_cannot_be_completed(self):
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(self.failed_report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.failed_report_run.refresh_from_db()
        self.assertEqual(self.failed_report_run.status, REPORT_RUN_STATUS_FAILED)
        self.assertFalse(
            DailyReport.objects.filter(report_run=self.failed_report_run).exists()
        )

    def test_completed_report_run_cannot_be_completed_again(self):
        DailyReport.objects.create(
            tenant=self.tenant,
            store=self.store,
            report_run=self.completed_report_run,
            content={"generated_at": "2026-06-25T10:00:00Z"},
            generated_at="2026-06-25T10:00:00Z",
        )
        token = self._mint_token()

        response = self.client.post(
            self._complete_url(self.completed_report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            DailyReport.objects.filter(report_run=self.completed_report_run).count(),
            1,
        )

    def test_invalid_report_payload_is_rejected(self):
        token = self._mint_token()
        body = self._valid_completion_body()
        body["report"] = "not-an-object"

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=body,
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DailyReport.objects.exists())

    def test_endpoint_does_not_create_actions(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()
        action_count_before = Action.objects.count()

        with patch.object(ActionService, "create_from_agent_payload") as create_mock:
            response = self.client.post(
                self._complete_url(report_run.id),
                data=body,
                format="json",
                **self._auth_header(token),
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        create_mock.assert_not_called()
        self.assertEqual(Action.objects.count(), action_count_before)

    def test_endpoint_does_not_mutate_actions(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()
        original_status = action.status

        with patch.object(ActionService, "approve") as approve_mock, patch.object(
            ActionService, "reject"
        ) as reject_mock, patch.object(
            ActionService, "queue_execution"
        ) as queue_mock:
            response = self.client.post(
                self._complete_url(report_run.id),
                data=body,
                format="json",
                **self._auth_header(token),
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        approve_mock.assert_not_called()
        reject_mock.assert_not_called()
        queue_mock.assert_not_called()

        action.refresh_from_db()
        self.assertEqual(action.status, original_status)
        self.assertIsNone(action.decided_by_id)
        self.assertIsNone(action.executed_at)

    def test_endpoint_delegates_to_report_run_service(self):
        report_run, agent_output, action = self._create_running_report_run_with_refs()
        body = self._valid_completion_body(
            report_run=report_run,
            agent_output=agent_output,
            action=action,
        )
        token = self._mint_token()

        with patch.object(
            ReportRunService,
            "complete_from_ai_payload",
            wraps=ReportRunService.complete_from_ai_payload,
        ) as mocked_complete:
            response = self.client.post(
                self._complete_url(report_run.id),
                data=body,
                format="json",
                **self._auth_header(token),
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_complete.assert_called_once()
        call_kwargs = mocked_complete.call_args.kwargs
        self.assertEqual(call_kwargs["tenant"].id, self.tenant.id)
        self.assertEqual(call_kwargs["store"].id, self.store.id)
        self.assertEqual(call_kwargs["service_name"], AI_SERVICE_COORDINATOR)

    def test_expired_service_jwt_is_rejected(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": AI_SERVICE_COORDINATOR,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "aud": TEST_JWT_SETTINGS["JWT_SERVICE_AUDIENCE"],
        }
        token = jwt.encode(
            payload,
            TEST_JWT_SETTINGS["JWT_SERVICE_SECRET"],
            algorithm=TEST_JWT_SETTINGS["JWT_SERVICE_ALGORITHM"],
        )

        response = self.client.post(
            self._complete_url(self.report_run.id),
            data=self._valid_completion_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
