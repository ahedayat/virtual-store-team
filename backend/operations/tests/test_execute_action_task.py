from config.celery import app as celery_app
from django.test import TestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.models import User, UserRole
from operations.constants import (
    ACTION_EVENT_TYPE_EXECUTED,
    ACTION_EVENT_TYPE_EXECUTING,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_EXECUTED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
)
from operations.models import Action, ActionEvent
from operations.services import ActionService
from operations.tasks import execute_action
from stores.models import Store
from tenants.models import Tenant


class ExecuteActionTaskTests(TestCase):
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
            password="test-password",
            tenant=self.tenant,
            role=UserRole.MANAGER,
        )

    def _valid_payload(self):
        return {
            "action_type": "sales.restock",
            "title": "Restock leather tote",
            "description": "Only 2 units remain.",
            "priority": 2,
            "payload": {"sku": "SKU-001", "suggested_order_qty": 10},
        }

    def _create_queued_action(self) -> Action:
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(),
        )
        approved = ActionService.approve(action=action, actor=self.manager)
        return ActionService.queue_execution(action=approved)

    def test_successful_execution_marks_action_executed(self):
        action = self._create_queued_action()

        result = execute_action(str(action.id))

        action.refresh_from_db()
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["action_id"], str(action.id))
        self.assertEqual(action.status, ACTION_STATUS_EXECUTED)
        self.assertIsNotNone(action.executed_at)
        self.assertEqual(action.execution_result["outcome"], "stubbed")
        self.assertEqual(
            ActionEvent.objects.filter(
                action=action,
                event_type=ACTION_EVENT_TYPE_EXECUTING,
            ).count(),
            1,
        )
        self.assertEqual(
            ActionEvent.objects.filter(
                action=action,
                event_type=ACTION_EVENT_TYPE_EXECUTED,
            ).count(),
            1,
        )

    def test_already_executed_action_is_idempotent(self):
        action = self._create_queued_action()
        first_result = execute_action(str(action.id))
        self.assertEqual(first_result["status"], "executed")

        second_result = execute_action(str(action.id))

        self.assertEqual(second_result["status"], "skipped")
        self.assertEqual(second_result["reason"], "already_executed")
        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_EXECUTED)
        self.assertEqual(
            ActionEvent.objects.filter(
                action=action,
                event_type=ACTION_EVENT_TYPE_EXECUTED,
            ).count(),
            1,
        )

    def test_pending_approval_action_is_not_executable(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(),
        )
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)

        result = execute_action(str(action.id))

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "not_executable")
        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)

    def test_approved_but_not_queued_action_is_not_executable(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(),
        )
        approved = ActionService.approve(action=action, actor=self.manager)
        self.assertEqual(approved.status, ACTION_STATUS_APPROVED)

        result = execute_action(str(approved.id))

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "not_executable")
        approved.refresh_from_db()
        self.assertEqual(approved.status, ACTION_STATUS_APPROVED)

    def test_missing_action_identifier_returns_skipped(self):
        missing_id = "00000000-0000-0000-0000-000000000099"

        result = execute_action(missing_id)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "action_not_found")

    def test_invalid_action_identifier_returns_skipped(self):
        result = execute_action("not-a-valid-uuid")

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "action_not_found")

    def test_task_is_registered_with_canonical_name(self):
        self.assertIn("actions.execute", celery_app.tasks)
        self.assertEqual(
            celery_app.tasks["actions.execute"].name,
            "actions.execute",
        )
