from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_TYPE_SALES_RESTOCK,
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_QUEUED,
)
from operations.history_constants import (
    HISTORY_TYPE_ACTION_CREATED,
    HISTORY_TYPE_ACTION_EVENT,
    HISTORY_TYPE_AGENT_OUTPUT_CREATED,
    HISTORY_TYPE_DAILY_REPORT_CREATED,
    HISTORY_TYPE_REPORT_RUN_COMPLETED,
    HISTORY_TYPE_REPORT_RUN_QUEUED,
)
from operations.models import Action, ActionEvent, AgentOutput, DailyReport, ReportRun
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
class HistoryFeedAPITests(APITestCase):
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
        self.tenant_manager = User.objects.create_user(
            email="tenant-manager@example.com",
            password="secure-pass-123",
            full_name="Tenant Manager",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=None,
        )
        self.history_url = reverse("api-history")
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)

    def _seed_scoped_records(self, *, store=None, tenant=None, suffix=""):
        tenant = tenant or self.tenant
        store = store or self.store
        now = timezone.now()

        report_run = ReportRun.objects.create(
            tenant=tenant,
            store=store,
            status=REPORT_RUN_STATUS_COMPLETED,
        )
        ReportRun.objects.filter(pk=report_run.pk).update(
            created_at=now - timedelta(hours=5),
            updated_at=now - timedelta(hours=1),
        )
        report_run.refresh_from_db()

        daily_report = DailyReport.objects.create(
            tenant=tenant,
            store=store,
            report_run=report_run,
            content={
                "operational_insights": ["Insight"],
                "prioritized_actions": [{"action_id": "x", "priority": 1, "summary": "s"}],
            },
            generated_at=now - timedelta(hours=1),
        )

        agent_output = AgentOutput.objects.create(
            tenant=tenant,
            store=store,
            report_run=report_run,
            agent_name=AI_SERVICE_SALES,
            output={
                "output_type": "sales_analysis",
                "payload": {
                    "customer_name": "Secret Customer",
                    "email": "secret@example.com",
                },
            },
        )
        AgentOutput.objects.filter(pk=agent_output.pk).update(
            created_at=now - timedelta(hours=2),
        )
        agent_output.refresh_from_db()

        action = Action.objects.create(
            tenant=tenant,
            store=store,
            report_run=report_run,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title=f"Restock item{suffix}",
            description=f"Low stock{suffix}",
            payload={"sku": "BAG-001", "customer_phone": "+989121234567"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        Action.objects.filter(pk=action.pk).update(created_at=now - timedelta(hours=3))
        action.refresh_from_db()

        ActionEvent.objects.create(
            action=action,
            event_type=ACTION_EVENT_TYPE_CREATED,
            previous_status="",
            new_status=ACTION_STATUS_PENDING_APPROVAL,
            reason="Created by agent",
            actor_type="agent",
            actor_id=AI_SERVICE_SALES,
            metadata={"action_type": ACTION_TYPE_SALES_RESTOCK},
        )
        created_event = ActionEvent.objects.filter(
            action=action, event_type=ACTION_EVENT_TYPE_CREATED
        ).first()
        ActionEvent.objects.filter(pk=created_event.pk).update(
            created_at=now - timedelta(hours=3, minutes=30),
        )

        approver = self.manager
        if tenant != self.tenant:
            approver = User.objects.create_user(
                email=f"foreign-manager{suffix}@example.com",
                password="secure-pass-123",
                role=UserRole.MANAGER,
                tenant=tenant,
                store=store,
            )

        ActionService.approve(
            action=action,
            actor=approver,
            reason="Manager approved a restock recommendation.",
        )
        approved_event = ActionEvent.objects.filter(
            action=action, event_type=ACTION_EVENT_TYPE_APPROVED
        ).first()
        ActionEvent.objects.filter(pk=approved_event.pk).update(
            created_at=now - timedelta(minutes=30),
        )

        queued_report_run = ReportRun.objects.create(
            tenant=tenant,
            store=store,
            status=REPORT_RUN_STATUS_QUEUED,
        )
        ReportRun.objects.filter(pk=queued_report_run.pk).update(
            created_at=now - timedelta(minutes=10),
        )

        return {
            "report_run": report_run,
            "daily_report": daily_report,
            "agent_output": agent_output,
            "action": action,
            "approved_event": approved_event,
            "queued_report_run": queued_report_run,
        }

    def test_authenticated_manager_can_access_history(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertGreater(response.data["count"], 0)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_service_jwt_cannot_access_history_endpoint(self):
        token = mint_service_jwt(
            service_name=AI_SERVICE_SALES,
            tenant_id=self.tenant_id,
            store_id=self.store_id,
        )

        response = self.client.get(
            self.history_url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_includes_report_run_items(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        types = {item["type"] for item in response.data["results"]}

        self.assertIn(HISTORY_TYPE_REPORT_RUN_COMPLETED, types)
        self.assertIn(HISTORY_TYPE_REPORT_RUN_QUEUED, types)
        report_run_ids = {
            item["report_run_id"]
            for item in response.data["results"]
            if item["type"].startswith("report_run_")
        }
        self.assertIn(str(records["report_run"].id), report_run_ids)

    def test_feed_includes_daily_report_items(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        daily_items = [
            item
            for item in response.data["results"]
            if item["type"] == HISTORY_TYPE_DAILY_REPORT_CREATED
        ]

        self.assertTrue(daily_items)
        self.assertEqual(daily_items[0]["daily_report_id"], str(records["daily_report"].id))

    def test_feed_includes_agent_output_items(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        output_items = [
            item
            for item in response.data["results"]
            if item["type"] == HISTORY_TYPE_AGENT_OUTPUT_CREATED
        ]

        self.assertTrue(output_items)
        self.assertEqual(output_items[0]["agent_name"], AI_SERVICE_SALES)
        self.assertEqual(output_items[0]["id"], f"agent_output:{records['agent_output'].id}")

    def test_feed_includes_action_items(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        action_items = [
            item
            for item in response.data["results"]
            if item["type"] == HISTORY_TYPE_ACTION_CREATED
        ]

        self.assertTrue(action_items)
        self.assertEqual(action_items[0]["action_id"], str(records["action"].id))

    def test_feed_includes_action_event_items(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        event_items = [
            item for item in response.data["results"] if item["type"] == HISTORY_TYPE_ACTION_EVENT
        ]

        self.assertGreaterEqual(len(event_items), 2)

    def test_feed_is_sorted_reverse_chronological(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        timestamps = [item["timestamp"] for item in response.data["results"]]

        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_feed_is_tenant_scoped(self):
        self._seed_scoped_records()
        self._seed_scoped_records(
            tenant=self.other_tenant,
            store=self.foreign_store,
            suffix="-foreign",
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)

        for item in response.data["results"]:
            if item.get("report_run_id"):
                report_run = ReportRun.objects.get(pk=item["report_run_id"])
                self.assertEqual(report_run.tenant_id, self.tenant.id)

    def test_cross_tenant_records_are_excluded(self):
        self._seed_scoped_records(
            tenant=self.other_tenant,
            store=self.foreign_store,
            suffix="-foreign",
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)

        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_store_scoping_is_enforced_for_store_scoped_user(self):
        self._seed_scoped_records(store=self.store)
        self._seed_scoped_records(store=self.other_store, suffix="-other-store")
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)

        self.assertGreater(response.data["count"], 0)
        for item in response.data["results"]:
            if item.get("action_id"):
                action = Action.objects.get(pk=item["action_id"])
                self.assertEqual(action.store_id, self.store.id)
            elif item.get("report_run_id"):
                report_run = ReportRun.objects.get(pk=item["report_run_id"])
                self.assertEqual(report_run.store_id, self.store.id)

    def test_tenant_wide_manager_sees_all_stores_in_tenant(self):
        self._seed_scoped_records(store=self.store)
        other_records = self._seed_scoped_records(store=self.other_store, suffix="-other")
        self.client.force_login(self.tenant_manager)

        response = self.client.get(self.history_url)

        action_ids = {
            item["action_id"] for item in response.data["results"] if item.get("action_id")
        }
        self.assertIn(str(other_records["action"].id), action_ids)

    def test_type_filter_works(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url, {"type": HISTORY_TYPE_ACTION_EVENT})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(item["type"] == HISTORY_TYPE_ACTION_EVENT for item in response.data["results"])
        )

    def test_status_filter_works(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url, {"status": ACTION_STATUS_APPROVED})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(item["status"] == ACTION_STATUS_APPROVED for item in response.data["results"])
        )

    def test_agent_name_filter_works(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url, {"agent_name": AI_SERVICE_SALES})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(item.get("agent_name") == AI_SERVICE_SALES for item in response.data["results"])
        )

    def test_report_run_id_filter_works(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(
            self.history_url,
            {"report_run_id": str(records["report_run"].id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(
                item.get("report_run_id") == str(records["report_run"].id)
                for item in response.data["results"]
            )
        )

    def test_action_id_filter_works(self):
        records = self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(
            self.history_url,
            {"action_id": str(records["action"].id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(item.get("action_id") == str(records["action"].id) for item in response.data["results"])
        )

    def test_date_range_filters_work(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        from_ts = (timezone.now() - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        to_ts = timezone.now().isoformat().replace("+00:00", "Z")

        response = self.client.get(
            self.history_url,
            {"from": from_ts, "to": to_ts},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["results"])

    def test_invalid_uuid_filter_returns_validation_error(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url, {"report_run_id": "not-a-uuid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_filter_returns_validation_error(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url, {"from": "not-a-date"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pagination_works(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        first_page = self.client.get(self.history_url, {"limit": 2, "offset": 0})
        second_page = self.client.get(self.history_url, {"limit": 2, "offset": 2})

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(first_page.data["results"]), 2)
        self.assertEqual(first_page.data["count"], second_page.data["count"])
        self.assertGreater(first_page.data["count"], 2)
        self.assertIsNotNone(first_page.data["next"])
        self.assertIsNone(first_page.data["previous"])
        self.assertIsNotNone(second_page.data["previous"])

        first_ids = {item["id"] for item in first_page.data["results"]}
        second_ids = {item["id"] for item in second_page.data["results"]}
        self.assertFalse(first_ids & second_ids)

    def test_raw_action_payload_is_not_exposed(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        body = str(response.data)

        self.assertNotIn("customer_phone", body)
        self.assertNotIn("BAG-001", body)

    def test_raw_agent_output_payload_is_not_exposed(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        response = self.client.get(self.history_url)
        body = str(response.data)

        self.assertNotIn("Secret Customer", body)
        self.assertNotIn("secret@example.com", body)

    def test_endpoint_does_not_mutate_records(self):
        self._seed_scoped_records()
        self.client.force_login(self.manager)

        counts_before = {
            "report_runs": ReportRun.objects.count(),
            "daily_reports": DailyReport.objects.count(),
            "agent_outputs": AgentOutput.objects.count(),
            "actions": Action.objects.count(),
            "action_events": ActionEvent.objects.count(),
        }

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ReportRun.objects.count(), counts_before["report_runs"])
        self.assertEqual(DailyReport.objects.count(), counts_before["daily_reports"])
        self.assertEqual(AgentOutput.objects.count(), counts_before["agent_outputs"])
        self.assertEqual(Action.objects.count(), counts_before["actions"])
        self.assertEqual(ActionEvent.objects.count(), counts_before["action_events"])

    def test_view_delegates_to_history_feed_service(self):
        self.client.force_login(self.manager)

        with patch(
            "operations.views.HistoryFeedService.list_for_user",
            return_value={"count": 0, "next": None, "previous": None, "results": []},
        ) as mock_list:
            response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_list.assert_called_once()
