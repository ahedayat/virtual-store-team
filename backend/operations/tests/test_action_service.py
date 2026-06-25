from accounts.constants import AI_SERVICE_SALES, AI_SERVICE_SUPPORT
from django.test import TestCase

from operations.constants import (
    ACTION_EVENT_TYPE_CREATED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_TYPE_CONTENT_INSTAGRAM_DRAFT,
    ACTION_TYPE_CONTENT_PRODUCT_DESCRIPTION,
    ACTION_TYPE_SALES_DISCOUNT,
    ACTION_TYPE_SALES_FOLLOW_UP,
    ACTION_TYPE_SALES_RESTOCK,
    ACTION_TYPE_SUPPORT_ESCALATE,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
    SUPPORTED_ACTION_TYPES,
)
from operations.exceptions import ActionPayloadValidationError, ActionScopeError
from operations.models import Action, ActionEvent, AgentOutput, ReportRun, ReportRunStatus
from operations.services import ActionService
from stores.models import Store
from tenants.models import Tenant


class ActionServiceCreateTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.other_tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.other_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Store B",
            slug="store-b",
            currency="USD",
        )
        self.report_run = ReportRun.objects.create(
            tenant=self.tenant,
            store=self.store,
            status=ReportRunStatus.RUNNING,
        )
        self.other_report_run = ReportRun.objects.create(
            tenant=self.other_tenant,
            store=self.other_store,
            status=ReportRunStatus.RUNNING,
        )

    def _valid_payload(self, **overrides):
        payload = {
            "action_type": ACTION_TYPE_SALES_RESTOCK,
            "title": "Restock leather tote",
            "description": "Only 2 units remain.",
            "priority": 2,
            "payload": {"sku": "SKU-001", "suggested_order_qty": 10},
        }
        payload.update(overrides)
        return payload

    def test_creates_pending_approval_action(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(requires_approval=True),
        )

        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertTrue(action.requires_approval)
        self.assertEqual(action.tenant_id, self.tenant.id)
        self.assertEqual(action.store_id, self.store.id)
        self.assertEqual(action.agent_name, AI_SERVICE_SALES)

    def test_creates_queued_action_when_auto_executable(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "Reply to sizing question",
                "description": "Draft a FAQ reply.",
                "priority": 3,
                "requires_approval": False,
                "low_risk": True,
                "payload": {"thread_id": "thread-1", "draft_text": "Hello"},
            },
        )

        self.assertEqual(action.status, ACTION_STATUS_QUEUED)
        self.assertFalse(action.requires_approval)

    def test_creates_exactly_one_initial_action_event(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(),
        )

        events = ActionEvent.objects.filter(action=action)
        self.assertEqual(events.count(), 1)

        event = events.get()
        self.assertEqual(event.event_type, ACTION_EVENT_TYPE_CREATED)
        self.assertEqual(event.previous_status, "")
        self.assertEqual(event.new_status, action.status)
        self.assertEqual(event.actor_id, AI_SERVICE_SALES)
        self.assertIn("requires manager approval", event.reason.lower())

    def test_rejects_invalid_action_type(self):
        with self.assertRaises(ActionPayloadValidationError) as ctx:
            ActionService.create_from_agent_payload(
                tenant=self.tenant,
                store=self.store,
                agent_name=AI_SERVICE_SALES,
                payload=self._valid_payload(action_type="sales.unknown"),
            )

        self.assertIn("Unsupported action_type", str(ctx.exception))
        self.assertEqual(Action.objects.count(), 0)

    def test_rejects_missing_required_fields(self):
        cases = [
            {"action_type": None},
            {"title": ""},
            {"description": "   "},
            {"priority": None},
        ]
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(ActionPayloadValidationError):
                    ActionService.create_from_agent_payload(
                        tenant=self.tenant,
                        store=self.store,
                        agent_name=AI_SERVICE_SALES,
                        payload=self._valid_payload(**override),
                    )

        self.assertEqual(Action.objects.count(), 0)

    def test_rejects_invalid_priority(self):
        for priority in [0, 6, "high", 3.5, True]:
            with self.subTest(priority=priority):
                with self.assertRaises(ActionPayloadValidationError):
                    ActionService.create_from_agent_payload(
                        tenant=self.tenant,
                        store=self.store,
                        agent_name=AI_SERVICE_SALES,
                        payload=self._valid_payload(priority=priority),
                    )

        self.assertEqual(Action.objects.count(), 0)

    def test_payload_tenant_store_ids_do_not_override_trusted_context(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(
                tenant_id=str(self.other_tenant.id),
                store_id=str(self.other_store.id),
            ),
        )

        self.assertEqual(action.tenant_id, self.tenant.id)
        self.assertEqual(action.store_id, self.store.id)

    def test_rejects_mismatched_report_run_scope(self):
        with self.assertRaises(ActionScopeError):
            ActionService.create_from_agent_payload(
                tenant=self.tenant,
                store=self.store,
                agent_name=AI_SERVICE_SALES,
                payload=self._valid_payload(),
                report_run=self.other_report_run,
            )

        self.assertEqual(Action.objects.count(), 0)

    def test_rejects_mismatched_source_agent_output_scope(self):
        other_output = AgentOutput.objects.create(
            tenant=self.other_tenant,
            store=self.other_store,
            agent_name=AI_SERVICE_SUPPORT,
            output={"summary": "other tenant"},
        )

        with self.assertRaises(ActionScopeError):
            ActionService.create_from_agent_payload(
                tenant=self.tenant,
                store=self.store,
                agent_name=AI_SERVICE_SALES,
                payload=self._valid_payload(),
                source_agent_output=other_output,
            )

        self.assertEqual(Action.objects.count(), 0)

    def test_default_policy_requires_approval_for_mvp_action_types(self):
        approval_required_types = [
            ACTION_TYPE_SALES_RESTOCK,
            ACTION_TYPE_SALES_DISCOUNT,
            ACTION_TYPE_SALES_FOLLOW_UP,
            ACTION_TYPE_CONTENT_INSTAGRAM_DRAFT,
            ACTION_TYPE_CONTENT_PRODUCT_DESCRIPTION,
            ACTION_TYPE_SUPPORT_ESCALATE,
        ]

        for action_type in approval_required_types:
            with self.subTest(action_type=action_type):
                action = ActionService.create_from_agent_payload(
                    tenant=self.tenant,
                    store=self.store,
                    agent_name=AI_SERVICE_SALES,
                    payload=self._valid_payload(action_type=action_type),
                )
                self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)
                self.assertTrue(action.requires_approval)

        self.assertEqual(len(approval_required_types), 6)
        self.assertEqual(len(SUPPORTED_ACTION_TYPES), 7)

    def test_support_reply_draft_low_risk_defaults_to_queued(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "FAQ reply",
                "description": "Answer sizing FAQ.",
                "priority": 4,
                "payload": {"low_risk": True, "draft_text": "Sizes run true."},
            },
        )

        self.assertEqual(action.status, ACTION_STATUS_QUEUED)
        self.assertFalse(action.requires_approval)

    def test_support_reply_draft_without_low_risk_stays_pending_approval(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SUPPORT,
            payload={
                "action_type": ACTION_TYPE_SUPPORT_REPLY_DRAFT,
                "title": "Refund reply",
                "description": "Draft mentions refund.",
                "priority": 1,
                "requires_approval": False,
                "payload": {"draft_text": "We can refund your order."},
            },
        )

        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertTrue(action.requires_approval)

    def test_accepts_matching_report_run(self):
        action = ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(),
            report_run=self.report_run,
        )

        self.assertEqual(action.report_run_id, self.report_run.id)
