from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES, AI_SERVICE_SUPPORT
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_REJECTED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_REJECTED,
    ACTION_TYPE_SALES_DISCOUNT,
    ACTION_TYPE_SALES_RESTOCK,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
)
from operations.models import Action, ActionEvent
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
class DashboardActionsAPITests(APITestCase):
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
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="secure-pass-123",
            full_name="Viewer Name",
            role=UserRole.VIEWER,
            tenant=self.tenant,
            store=self.store,
        )
        self.foreign_manager = User.objects.create_user(
            email="foreign@example.com",
            password="secure-pass-123",
            full_name="Foreign Manager",
            role=UserRole.MANAGER,
            tenant=self.other_tenant,
            store=self.foreign_store,
        )
        self.list_url = reverse("api-actions-list")
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)

    def _valid_payload(self, **overrides):
        payload = {
            "action_type": ACTION_TYPE_SALES_RESTOCK,
            "title": "Restock leather tote",
            "description": "Only 2 units remain.",
            "priority": 2,
            "payload": {
                "sku": "SKU-001",
                "suggested_order_qty": 10,
                "customer_phone": "+989121234567",
                "draft_text": "Sensitive draft body",
            },
        }
        payload.update(overrides)
        return payload

    def _create_action(self, *, store=None, **payload_overrides):
        store = store or self.store
        return ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(**payload_overrides),
        )

    def test_authenticated_list_access(self):
        action = self._create_action()
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["id"], str(action.id))
        self.assertEqual(item["status"], ACTION_STATUS_PENDING_APPROVAL)
        self.assertEqual(item["agent_name"], AI_SERVICE_SALES)
        self.assertIn("payload_summary", item)
        self.assertEqual(item["payload_summary"]["sku"], "SKU-001")
        self.assertNotIn("customer_phone", item["payload_summary"])
        self.assertNotIn("draft_text", item["payload_summary"])

    def test_authenticated_detail_access(self):
        action = self._create_action()
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-actions-detail", kwargs={"action_id": action.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(action.id))
        self.assertEqual(response.data["action_type"], ACTION_TYPE_SALES_RESTOCK)
        self.assertIsNone(response.data["decided_by"])
        self.assertIsNone(response.data["decided_at"])

    def test_filter_by_status_pending_approval(self):
        pending = self._create_action()
        approved = self._create_action(title="Discount promo")
        ActionService.approve(action=approved, actor=self.manager)
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url, {"status": ACTION_STATUS_PENDING_APPROVAL})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(pending.id))

    def test_filter_by_action_type(self):
        restock = self._create_action()
        ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "Reply draft",
                "description": "Draft a reply.",
                "priority": 3,
                "requires_approval": True,
                "payload": {"thread_id": "thread-1"},
            },
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url, {"action_type": ACTION_TYPE_SALES_RESTOCK})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(restock.id))

    def test_filter_by_agent_name(self):
        self._create_action()
        ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "Reply draft",
                "description": "Draft a reply.",
                "priority": 3,
                "requires_approval": True,
                "payload": {"thread_id": "thread-1"},
            },
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url, {"agent": AI_SERVICE_SUPPORT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["agent_name"], AI_SERVICE_SUPPORT)

    def test_filter_by_requires_approval(self):
        self._create_action(requires_approval=True)
        ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "Auto reply",
                "description": "Low risk reply.",
                "priority": 3,
                "requires_approval": False,
                "low_risk": True,
                "payload": {"thread_id": "thread-2"},
            },
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url, {"requires_approval": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertTrue(response.data["results"][0]["requires_approval"])

    def test_store_isolation_on_list(self):
        self._create_action(store=self.store)
        self._create_action(store=self.other_store, title="Other store action")
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["store_id"], str(self.store.id))

    def test_cross_tenant_detail_returns_404(self):
        foreign_action = ActionService.create_from_agent_payload(
            tenant=self.other_tenant,
            store=self.foreign_store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(action_type=ACTION_TYPE_SALES_DISCOUNT),
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-actions-detail", kwargs={"action_id": foreign_action.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_list_is_rejected(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_service_jwt_cannot_access_actions_list(self):
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

    def test_list_ordered_newest_first(self):
        older = self._create_action(title="Older action")
        Action.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        newer = self._create_action(title="Newer action")
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids[0], str(newer.id))


@override_settings(**TEST_JWT_SETTINGS)
class ActionDecisionAPITests(APITestCase):
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
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="secure-pass-123",
            full_name="Viewer Name",
            role=UserRole.VIEWER,
            tenant=self.tenant,
            store=self.store,
        )
        self.foreign_manager = User.objects.create_user(
            email="foreign@example.com",
            password="secure-pass-123",
            full_name="Foreign Manager",
            role=UserRole.MANAGER,
            tenant=self.other_tenant,
            store=self.foreign_store,
        )

    def _create_pending_action(self, *, store=None):
        store = store or self.store
        return ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=store,
            agent_name=AI_SERVICE_SALES,
            payload={
                "action_type": ACTION_TYPE_SALES_RESTOCK,
                "title": "Restock leather tote",
                "description": "Only 2 units remain.",
                "priority": 2,
                "payload": {"sku": "SKU-001"},
            },
        )

    def test_manager_can_approve_pending_action(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-approve", kwargs={"action_id": action.id}),
            {"reason": "Looks good."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ACTION_STATUS_APPROVED)
        self.assertEqual(response.data["decided_by"]["id"], str(self.manager.id))
        self.assertIsNotNone(response.data["decided_at"])

    def test_manager_can_reject_pending_action_with_reason(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-reject", kwargs={"action_id": action.id}),
            {"reason": "Not needed this week."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ACTION_STATUS_REJECTED)
        self.assertEqual(response.data["status_reason"], "Not needed this week.")

    def test_reject_without_reason_fails(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-reject", kwargs={"action_id": action.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_status_transition_fails(self):
        action = self._create_pending_action()
        ActionService.approve(action=action, actor=self.manager)
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-reject", kwargs={"action_id": action.id}),
            {"reason": "Too late."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_viewer_cannot_approve(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(
            reverse("api-actions-approve", kwargs={"action_id": action.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_reject(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post(
            reverse("api-actions-reject", kwargs={"action_id": action.id}),
            {"reason": "Nope."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_approve_returns_404(self):
        foreign_action = ActionService.create_from_agent_payload(
            tenant=self.other_tenant,
            store=self.foreign_store,
            agent_name=AI_SERVICE_SALES,
            payload={
                "action_type": ACTION_TYPE_SALES_RESTOCK,
                "title": "Foreign restock",
                "description": "Foreign store.",
                "priority": 1,
                "payload": {"sku": "SKU-FOREIGN"},
            },
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-approve", kwargs={"action_id": foreign_action.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_store_approve_returns_404(self):
        action = self._create_pending_action(store=self.other_store)
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("api-actions-approve", kwargs={"action_id": action.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_approve_creates_audit_event(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.manager)

        self.client.post(
            reverse("api-actions-approve", kwargs={"action_id": action.id}),
            {},
            format="json",
        )

        event = ActionEvent.objects.get(action=action, event_type=ACTION_EVENT_TYPE_APPROVED)
        self.assertEqual(event.new_status, ACTION_STATUS_APPROVED)
        self.assertEqual(event.actor_id, str(self.manager.id))

    def test_reject_creates_audit_event(self):
        action = self._create_pending_action()
        self.client.force_authenticate(user=self.manager)

        self.client.post(
            reverse("api-actions-reject", kwargs={"action_id": action.id}),
            {"reason": "Duplicate recommendation."},
            format="json",
        )

        event = ActionEvent.objects.get(action=action, event_type=ACTION_EVENT_TYPE_REJECTED)
        self.assertEqual(event.new_status, ACTION_STATUS_REJECTED)
        self.assertEqual(event.reason, "Duplicate recommendation.")
