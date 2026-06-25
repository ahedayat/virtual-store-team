from accounts.constants import AI_SERVICE_SALES, AI_SERVICE_SUPPORT
from accounts.models import User, UserRole
from accounts.service_identity import AIServiceIdentity
from django.test import TestCase
from django.utils import timezone

from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_EVENT_TYPE_QUEUED,
    ACTION_EVENT_TYPE_REJECTED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_STATUS_REJECTED,
    ACTION_TYPE_CONTENT_INSTAGRAM_DRAFT,
    ACTION_TYPE_CONTENT_PRODUCT_DESCRIPTION,
    ACTION_TYPE_SALES_DISCOUNT,
    ACTION_TYPE_SALES_FOLLOW_UP,
    ACTION_TYPE_SALES_RESTOCK,
    ACTION_TYPE_SUPPORT_ESCALATE,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
    SUPPORTED_ACTION_TYPES,
)
from operations.exceptions import ActionPayloadValidationError, ActionScopeError, ActionTransitionError
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


class ActionServiceTransitionTests(TestCase):
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
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="secure-pass-123",
            full_name="Manager Name",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        self.other_manager = User.objects.create_user(
            email="other-manager@example.com",
            password="secure-pass-123",
            full_name="Other Manager",
            role=UserRole.MANAGER,
            tenant=self.other_tenant,
            store=self.other_store,
        )
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="secure-pass-123",
            full_name="Viewer Name",
            role=UserRole.VIEWER,
            tenant=self.tenant,
            store=self.store,
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

    def _create_pending_action(self, **payload_overrides):
        return ActionService.create_from_agent_payload(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            payload=self._valid_payload(**payload_overrides),
        )

    def _create_approved_action(self, **payload_overrides):
        action = self._create_pending_action(**payload_overrides)
        return ActionService.approve(action=action, actor=self.manager)

    def test_approve_pending_action_changes_status_to_approved(self):
        action = self._create_pending_action()

        approved = ActionService.approve(action=action, actor=self.manager)

        self.assertEqual(approved.status, ACTION_STATUS_APPROVED)

    def test_reject_pending_action_changes_status_to_rejected(self):
        action = self._create_pending_action()

        rejected = ActionService.reject(
            action=action,
            actor=self.manager,
            reason="Not needed this week.",
        )

        self.assertEqual(rejected.status, ACTION_STATUS_REJECTED)

    def test_queue_execution_changes_approved_action_to_queued(self):
        action = self._create_approved_action()

        queued = ActionService.queue_execution(action=action)

        self.assertEqual(queued.status, ACTION_STATUS_QUEUED)

    def test_approve_sets_decided_by_and_decided_at(self):
        action = self._create_pending_action()
        before = timezone.now()

        approved = ActionService.approve(action=action, actor=self.manager)
        after = timezone.now()

        self.assertEqual(approved.decided_by_id, self.manager.id)
        self.assertIsNotNone(approved.decided_at)
        self.assertGreaterEqual(approved.decided_at, before)
        self.assertLessEqual(approved.decided_at, after)

    def test_reject_sets_decided_by_decided_at_and_reason(self):
        action = self._create_pending_action()

        rejected = ActionService.reject(
            action=action,
            actor=self.manager,
            reason="Duplicate recommendation.",
        )

        self.assertEqual(rejected.decided_by_id, self.manager.id)
        self.assertIsNotNone(rejected.decided_at)
        self.assertEqual(rejected.status_reason, "Duplicate recommendation.")

    def test_each_successful_transition_creates_exactly_one_action_event(self):
        action = self._create_pending_action()
        initial_event_count = ActionEvent.objects.filter(action=action).count()
        self.assertEqual(initial_event_count, 1)

        approved = ActionService.approve(action=action, actor=self.manager)
        self.assertEqual(ActionEvent.objects.filter(action=approved).count(), 2)

        approve_event = (
            ActionEvent.objects.filter(action=approved, event_type=ACTION_EVENT_TYPE_APPROVED)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(approve_event)
        self.assertEqual(approve_event.previous_status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertEqual(approve_event.new_status, ACTION_STATUS_APPROVED)
        self.assertEqual(approve_event.actor_id, str(self.manager.id))

        queued = ActionService.queue_execution(action=approved)
        self.assertEqual(ActionEvent.objects.filter(action=queued).count(), 3)

        queue_event = (
            ActionEvent.objects.filter(action=queued, event_type=ACTION_EVENT_TYPE_QUEUED)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(queue_event)
        self.assertEqual(queue_event.previous_status, ACTION_STATUS_APPROVED)
        self.assertEqual(queue_event.new_status, ACTION_STATUS_QUEUED)

    def test_approve_non_pending_action_fails(self):
        action = self._create_approved_action()
        approve_event_count_before = ActionEvent.objects.filter(
            action=action,
            event_type=ACTION_EVENT_TYPE_APPROVED,
        ).count()

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.approve(action=action, actor=self.manager)

        self.assertIn("approved", str(ctx.exception))
        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_APPROVED)
        self.assertEqual(
            ActionEvent.objects.filter(
                action=action,
                event_type=ACTION_EVENT_TYPE_APPROVED,
            ).count(),
            approve_event_count_before,
        )

    def test_reject_non_pending_action_fails(self):
        action = self._create_approved_action()

        with self.assertRaises(ActionTransitionError):
            ActionService.reject(action=action, actor=self.manager, reason="Too late.")

        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_APPROVED)

    def test_queue_non_approved_action_fails(self):
        action = self._create_pending_action()

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.queue_execution(action=action)

        self.assertIn("queued", str(ctx.exception))
        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)

    def test_rejected_actions_are_terminal(self):
        action = self._create_pending_action()
        rejected = ActionService.reject(
            action=action,
            actor=self.manager,
            reason="Declined.",
        )

        for method, kwargs in [
            (ActionService.approve, {"actor": self.manager}),
            (ActionService.reject, {"actor": self.manager, "reason": "Again"}),
            (ActionService.queue_execution, {}),
        ]:
            with self.subTest(method=method.__name__):
                with self.assertRaises(ActionTransitionError):
                    method(action=rejected, **kwargs)

        rejected.refresh_from_db()
        self.assertEqual(rejected.status, ACTION_STATUS_REJECTED)

    def test_other_tenant_actor_cannot_approve_or_reject(self):
        action = self._create_pending_action()

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.approve(action=action, actor=self.other_manager)

        self.assertIn("same tenant", str(ctx.exception))

        with self.assertRaises(ActionTransitionError):
            ActionService.reject(
                action=action,
                actor=self.other_manager,
                reason="Cross-tenant reject.",
            )

        action.refresh_from_db()
        self.assertEqual(action.status, ACTION_STATUS_PENDING_APPROVAL)

    def test_service_identity_cannot_approve_or_reject(self):
        action = self._create_pending_action()
        service_identity = AIServiceIdentity(
            service_name=AI_SERVICE_SALES,
            tenant_id=str(self.tenant.id),
            store_id=str(self.store.id),
        )

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.approve(action=action, actor=service_identity)  # type: ignore[arg-type]

        self.assertIn("human user", str(ctx.exception))

        with self.assertRaises(ActionTransitionError):
            ActionService.reject(
                action=action,
                actor=service_identity,  # type: ignore[arg-type]
                reason="Agent reject.",
            )

    def test_viewer_cannot_approve_or_reject(self):
        action = self._create_pending_action()

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.approve(action=action, actor=self.viewer)

        self.assertIn("managers or staff", str(ctx.exception))

        with self.assertRaises(ActionTransitionError):
            ActionService.reject(
                action=action,
                actor=self.viewer,
                reason="Viewer reject.",
            )

    def test_queue_execution_does_not_execute_or_set_executed_at(self):
        action = self._create_approved_action()

        queued = ActionService.queue_execution(
            action=action,
            reason="Ready for worker.",
            metadata={"source": "test"},
        )

        self.assertIsNone(queued.executed_at)
        self.assertIsNone(queued.execution_result)
        self.assertEqual(queued.status, ACTION_STATUS_QUEUED)

    def test_cannot_approve_or_reject_already_queued_action(self):
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

        with self.assertRaises(ActionTransitionError):
            ActionService.approve(action=action, actor=self.manager)

        with self.assertRaises(ActionTransitionError):
            ActionService.reject(action=action, actor=self.manager, reason="Too late.")

    def test_queue_execution_on_already_queued_action_raises_transition_error(self):
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

        with self.assertRaises(ActionTransitionError) as ctx:
            ActionService.queue_execution(action=action)

        self.assertIn("approved", str(ctx.exception))

    def test_reject_event_records_reason_and_metadata(self):
        action = self._create_pending_action()

        rejected = ActionService.reject(
            action=action,
            actor=self.manager,
            reason="Budget constraints.",
            metadata={"channel": "dashboard"},
        )

        event = ActionEvent.objects.get(action=rejected, event_type=ACTION_EVENT_TYPE_REJECTED)
        self.assertEqual(event.reason, "Budget constraints.")
        self.assertEqual(event.metadata, {"channel": "dashboard"})
        self.assertEqual(event.previous_status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertEqual(event.new_status, ACTION_STATUS_REJECTED)
