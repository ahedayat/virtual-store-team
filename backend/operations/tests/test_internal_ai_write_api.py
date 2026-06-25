from unittest.mock import patch

import jwt
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from operations.constants import (
    ACTION_EVENT_TYPE_CREATED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_TYPE_SALES_RESTOCK,
    REPORT_RUN_STATUS_RUNNING,
)
from operations.models import Action, ActionEvent, AgentOutput, ReportRun
from operations.services import ActionService
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}


@override_settings(**TEST_JWT_SETTINGS)
class InternalActionCreateAPITests(APITestCase):
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
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)
        self.actions_url = reverse("internal-ai-actions-create")

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_SALES),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _valid_action_body(self, **overrides):
        body = {
            "action_type": ACTION_TYPE_SALES_RESTOCK,
            "title": "Restock: Leather Tote Model A",
            "description": "Only 2 units left; sold 14 in the last 7 days.",
            "priority": 1,
            "requires_approval": True,
            "payload": {
                "sku": "BAG-001",
                "current_stock": 2,
                "suggested_order_qty": 20,
            },
        }
        body.update(overrides)
        return body

    def test_valid_service_jwt_can_create_action(self):
        token = self._mint_token()

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(report_run_id=str(self.report_run.id)),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["action_type"], ACTION_TYPE_SALES_RESTOCK)
        self.assertEqual(response.data["status"], ACTION_STATUS_PENDING_APPROVAL)
        self.assertEqual(response.data["agent_name"], AI_SERVICE_SALES)
        self.assertEqual(str(response.data["report_run_id"]), str(self.report_run.id))
        self.assertTrue(Action.objects.filter(id=response.data["id"]).exists())

    def test_missing_token_is_rejected(self):
        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_is_rejected(self):
        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(),
            format="json",
            HTTP_AUTHORIZATION="Bearer not-a-valid-jwt",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_authenticated_user_cannot_create_action(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_action_uses_tenant_store_from_jwt_not_request_body(self):
        token = self._mint_token()
        foreign_tenant_id = str(self.other_tenant.id)
        foreign_store_id = str(self.foreign_store.id)

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(
                tenant_id=foreign_tenant_id,
                store_id=foreign_store_id,
            ),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        action = Action.objects.get(id=response.data["id"])
        self.assertEqual(action.tenant_id, self.tenant.id)
        self.assertEqual(action.store_id, self.store.id)
        self.assertNotEqual(action.tenant_id, self.other_tenant.id)

    def test_cross_tenant_report_run_id_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(
                report_run_id=str(self.other_report_run.id),
            ),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Action.objects.exists())

    def test_cross_store_report_run_id_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(
                report_run_id=str(self.other_store_report_run.id),
            ),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Action.objects.exists())

    def test_invalid_action_payload_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(action_type="invalid.type"),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Action.objects.exists())

    def test_action_endpoint_delegates_to_action_service(self):
        token = self._mint_token()
        body = self._valid_action_body()

        with patch.object(
            ActionService,
            "create_from_agent_payload",
            wraps=ActionService.create_from_agent_payload,
        ) as mocked_create:
            response = self.client.post(
                self.actions_url,
                data=body,
                format="json",
                **self._auth_header(token),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mocked_create.assert_called_once()
        call_kwargs = mocked_create.call_args.kwargs
        self.assertEqual(call_kwargs["tenant"].id, self.tenant.id)
        self.assertEqual(call_kwargs["store"].id, self.store.id)
        self.assertEqual(call_kwargs["agent_name"], AI_SERVICE_SALES)
        self.assertEqual(call_kwargs["payload"]["action_type"], ACTION_TYPE_SALES_RESTOCK)

    def test_created_action_receives_initial_status_from_service(self):
        token = self._mint_token()

        response = self.client.post(
            self.actions_url,
            data=self._valid_action_body(requires_approval=True),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        action = Action.objects.get(id=response.data["id"])
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertEqual(action.events.count(), 1)
        self.assertEqual(action.events.get().event_type, ACTION_EVENT_TYPE_CREATED)

    def test_action_endpoint_does_not_approve_reject_or_execute(self):
        token = self._mint_token()

        with patch.object(ActionService, "approve") as approve_mock, patch.object(
            ActionService, "reject"
        ) as reject_mock, patch.object(
            ActionService, "queue_execution"
        ) as queue_mock:
            response = self.client.post(
                self.actions_url,
                data=self._valid_action_body(requires_approval=True),
                format="json",
                **self._auth_header(token),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        approve_mock.assert_not_called()
        reject_mock.assert_not_called()
        queue_mock.assert_not_called()

        action = Action.objects.get(id=response.data["id"])
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertIsNone(action.decided_by_id)
        self.assertIsNone(action.executed_at)


@override_settings(**TEST_JWT_SETTINGS)
class InternalAgentOutputCreateAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.other_tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.foreign_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Foreign Store",
            slug="foreign",
            currency="EUR",
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
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)
        self.agent_outputs_url = reverse("internal-ai-agent-outputs-create")

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_SALES),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _valid_output_body(self, **overrides):
        body = {
            "output_type": "sales_analysis",
            "payload": {
                "summary": "Sales increased for top products.",
                "recommendations": [],
            },
            "metadata": {
                "model": "mock",
                "duration_ms": 1200,
            },
        }
        body.update(overrides)
        return body

    def test_valid_service_jwt_can_create_agent_output(self):
        token = self._mint_token()

        response = self.client.post(
            self.agent_outputs_url,
            data=self._valid_output_body(report_run_id=str(self.report_run.id)),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["output_type"], "sales_analysis")
        self.assertEqual(response.data["agent_name"], AI_SERVICE_SALES)
        self.assertEqual(str(response.data["report_run_id"]), str(self.report_run.id))
        self.assertTrue(AgentOutput.objects.filter(id=response.data["id"]).exists())

    def test_invalid_agent_output_payload_is_rejected(self):
        token = self._mint_token()

        response = self.client.post(
            self.agent_outputs_url,
            data=self._valid_output_body(payload="not-an-object"),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(AgentOutput.objects.exists())

    def test_agent_output_uses_authenticated_service_name(self):
        token = self._mint_token(service_name=AI_SERVICE_SALES)

        response = self.client.post(
            self.agent_outputs_url,
            data=self._valid_output_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        agent_output = AgentOutput.objects.get(id=response.data["id"])
        self.assertEqual(agent_output.agent_name, AI_SERVICE_SALES)

    def test_cross_tenant_report_run_id_is_rejected_for_agent_output(self):
        token = self._mint_token()

        response = self.client.post(
            self.agent_outputs_url,
            data=self._valid_output_body(
                report_run_id=str(self.other_report_run.id),
            ),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(AgentOutput.objects.exists())

    def test_agent_output_endpoint_does_not_complete_reports(self):
        token = self._mint_token()
        original_status = self.report_run.status

        response = self.client.post(
            self.agent_outputs_url,
            data=self._valid_output_body(report_run_id=str(self.report_run.id)),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.report_run.refresh_from_db()
        self.assertEqual(self.report_run.status, original_status)

    def test_expired_service_jwt_is_rejected(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": AI_SERVICE_SALES,
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
            self.agent_outputs_url,
            data=self._valid_output_body(),
            format="json",
            **self._auth_header(token),
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
