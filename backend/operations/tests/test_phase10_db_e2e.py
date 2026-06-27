"""DB-backed Phase 10 E2E verification (Step 10.7)."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import LiveServerTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.constants import AI_SERVICE_SALES
from accounts.models import User, UserRole
from catalog.models import (
    Customer,
    InventoryLevel,
    Message,
    MessageDirection,
    MessageThread,
    Order,
    OrderItem,
    OrderStatus,
    Platform,
    Product,
    SenderType,
)
from operations.constants import (
    ACTION_STATUS_EXECUTED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_TYPE_SALES_RESTOCK,
    REPORT_RUN_STATUS_COMPLETED,
)
from operations.models import Action, AgentOutput, DailyReport, ReportRun
from operations.tests.phase10_e2e_harness import WorkflowCoordinatorBridgeServer
from stores.models import Store
from tenants.models import Tenant
from agents.coordinator.config import CoordinatorNodeTimeouts
from agents.coordinator.tests.integration_harness import (
    CONTENT_HOST,
    SALES_HOST,
    SUPPORT_HOST,
    ServiceRouterTransport,
)
from agents.coordinator.topology import assert_star_topology

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
    "COORDINATOR_DAILY_REPORT_PATH": "/workflows/daily-report",
    "COORDINATOR_HTTP_TIMEOUT_SECONDS": 120,
}

EAGER_CELERY_SETTINGS = {
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_TASK_EAGER_PROPAGATES": True,
}

REQUIRED_REPORT_SECTIONS = frozenset(
    {
        "sales_summary",
        "prioritized_actions",
        "content_suggestions",
        "support_insights",
        "next_steps",
        "agent_outputs_ref",
    }
)

PII_MARKERS = (
    "customer@example.com",
    "+98-912-345-6789",
    "Bearer service-jwt",
    "09121234567",
)


def _integration_settings(live_server_url: str, coordinator_url: str):
    return override_settings(
        **TEST_JWT_SETTINGS,
        **EAGER_CELERY_SETTINGS,
        COORDINATOR_AGENT_URL=coordinator_url.rsplit("/workflows", 1)[0],
        COORDINATOR_DAILY_REPORT_URL=coordinator_url,
    )


class Phase10DbBackedE2ESuccessTests(LiveServerTestCase):
    """Prove Celery → coordinator graph → specialists → Django completion with real DB rows."""

    host = "127.0.0.1"
    @classmethod
    def setUpClass(cls):
        cls._env_patcher = patch.dict(
            os.environ,
            {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""},
            clear=False,
        )
        cls._env_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._env_patcher.stop()

    def setUp(self):
        self.api_client = APIClient()
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
            timezone="America/New_York",
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="secure-pass-123",
            full_name="Manager Name",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Canvas Tote",
            slug="canvas-tote",
            sku="TOTE-001",
            price=Decimal("50.00"),
        )
        self._seed_store_context_data()
        self.pending_action = Action.objects.create(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Restock tote",
            description="Low stock threshold reached.",
            payload={"sku": "TOTE-001"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        self.generate_url = reverse("api-reports-generate")
        self.coordinator_bridge = WorkflowCoordinatorBridgeServer(
            django_base_url=self.live_server_url,
            transport_factory=lambda: ServiceRouterTransport(),
        )
        self.coordinator_bridge.start()

    def tearDown(self):
        self.coordinator_bridge.stop()

    def _seed_store_context_data(self) -> None:
        placed_at = timezone.now().astimezone(ZoneInfo("America/New_York")).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number="ORD-E2E-1",
            status=OrderStatus.PAID,
            currency="USD",
            subtotal_amount=Decimal("50.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("50.00"),
            placed_at=placed_at,
            external_customer_ref="opaque-ref",
        )
        OrderItem.objects.create(
            tenant=self.tenant,
            store=self.store,
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            sku_snapshot=self.product.sku,
            quantity=1,
            unit_price=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )
        InventoryLevel.objects.create(
            tenant=self.tenant,
            store=self.store,
            product=self.product,
            quantity_on_hand=2,
            reserved_quantity=0,
            low_stock_threshold=5,
        )
        customer = Customer.objects.create(
            tenant=self.tenant,
            store=self.store,
            display_name="Customer A",
            email="customer@example.com",
            phone="09121234567",
            platform=Platform.INSTAGRAM,
        )
        thread = MessageThread.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer=customer,
            platform=Platform.INSTAGRAM,
            external_thread_id="thread-e2e-1",
            status="open",
            last_message_at=timezone.now(),
        )
        Message.objects.create(
            tenant=self.tenant,
            store=self.store,
            thread=thread,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            body="What are your store hours?",
            sent_at=timezone.now(),
        )

    def test_celery_coordinator_graph_persists_completed_report_run_and_daily_report(self):
        with _integration_settings(
            self.live_server_url,
            self.coordinator_bridge.daily_report_url,
        ):
            self.api_client.force_authenticate(user=self.manager)
            response = self.api_client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)
        self.assertEqual(report_run.error_message, "")

        daily_report = DailyReport.objects.get(report_run=report_run)
        report_content = daily_report.content
        self.assertTrue(isinstance(report_content, dict))

        for section in REQUIRED_REPORT_SECTIONS:
            self.assertIn(section, report_content, msg=f"Missing section: {section}")

        self.assertIsInstance(report_content["sales_summary"], dict)
        self.assertIsInstance(report_content["prioritized_actions"], list)
        self.assertIsInstance(report_content["content_suggestions"], list)
        self.assertIsInstance(report_content["support_insights"], list)
        self.assertTrue(report_content["support_insights"])
        self.assertIsInstance(report_content["next_steps"], list)
        agent_outputs_ref = report_content["agent_outputs_ref"]
        self.assertIsInstance(agent_outputs_ref, list)
        self.assertEqual(len(agent_outputs_ref), 3)

        persisted_outputs = list(
            AgentOutput.objects.filter(report_run=report_run).order_by("created_at")
        )
        self.assertEqual(len(persisted_outputs), 3)
        persisted_ids = {str(item.id) for item in persisted_outputs}
        self.assertEqual(set(agent_outputs_ref), persisted_ids)

        workflow_deps = self.coordinator_bridge.last_workflow_deps
        self.assertIsNotNone(workflow_deps)
        assert workflow_deps is not None

        specialist_hosts = {SALES_HOST, CONTENT_HOST, SUPPORT_HOST}
        specialist_calls = [
            entry
            for entry in workflow_deps.transport.request_log
            if entry["host"] in specialist_hosts and entry["path"] == "/run"
        ]
        self.assertEqual(len(specialist_calls), 3)

        django_internal_calls = [
            entry
            for entry in workflow_deps.transport.request_log
            if entry["host"] not in specialist_hosts
            and entry["path"].startswith("/internal/ai/")
        ]
        self.assertTrue(any("/context/" in entry["path"] for entry in django_internal_calls))
        self.assertTrue(
            any(entry["path"].endswith("/agent-outputs/") for entry in django_internal_calls)
        )
        self.assertTrue(
            any("/report-runs/" in entry["path"] and entry["path"].endswith("/complete/")
                for entry in django_internal_calls)
        )
        self.assertFalse(
            any("/actions/" in entry["path"] for entry in django_internal_calls),
            "Coordinator must not call Django action mutation endpoints.",
        )

        self.pending_action.refresh_from_db()
        self.assertEqual(self.pending_action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertFalse(
            Action.objects.filter(status=ACTION_STATUS_EXECUTED).exists()
        )
        self.assertFalse(
            Action.objects.filter(status=ACTION_STATUS_QUEUED).exists()
        )

        warnings_blob = json.dumps(report_content.get("warnings", []))
        for marker in PII_MARKERS:
            self.assertNotIn(marker, warnings_blob)

        assert_star_topology()


class Phase10DbBackedE2EPartialFailureTests(LiveServerTestCase):
    """Prove partial specialist failure still completes with warnings and consistent DB state."""

    host = "127.0.0.1"
    @classmethod
    def setUpClass(cls):
        cls._env_patcher = patch.dict(
            os.environ,
            {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""},
            clear=False,
        )
        cls._env_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._env_patcher.stop()

    def setUp(self):
        self.api_client = APIClient()
        self.tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store B",
            slug="store-b",
            currency="USD",
            timezone="UTC",
        )
        self.manager = User.objects.create_user(
            email="manager-b@example.com",
            password="secure-pass-123",
            full_name="Manager B",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Weekender Bag",
            slug="weekender-bag",
            sku="BAG-002",
            price=Decimal("80.00"),
        )
        self.generate_url = reverse("api-reports-generate")
        self.coordinator_bridge = WorkflowCoordinatorBridgeServer(
            django_base_url=self.live_server_url,
            transport_factory=lambda: ServiceRouterTransport(content_delay_seconds=0.25),
            node_timeouts=CoordinatorNodeTimeouts(
                fetch_context_seconds=5.0,
                sales_seconds=5.0,
                content_seconds=0.05,
                support_seconds=5.0,
                merge_seconds=5.0,
                submit_seconds=5.0,
            ),
        )
        self.coordinator_bridge.start()

    def tearDown(self):
        self.coordinator_bridge.stop()

    def test_content_timeout_produces_partial_report_with_warnings(self):
        with _integration_settings(
            self.live_server_url,
            self.coordinator_bridge.daily_report_url,
        ):
            self.api_client.force_authenticate(user=self.manager)
            response = self.api_client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(report_run.status, REPORT_RUN_STATUS_COMPLETED)

        daily_report = DailyReport.objects.get(report_run=report_run)
        report_content = daily_report.content
        self.assertTrue(report_content.get("partial"))
        self.assertIn("warnings", report_content)
        warning_codes = {item["code"] for item in report_content["warnings"]}
        self.assertIn("specialist_node_timeout", warning_codes)

        self.assertIn("sales_summary", report_content)
        self.assertTrue(report_content["sales_summary"])
        self.assertIn("support_insights", report_content)
        self.assertTrue(report_content["support_insights"])
        self.assertIn("content", report_content.get("missing_sections", []))

        persisted_outputs = AgentOutput.objects.filter(report_run=report_run)
        self.assertEqual(persisted_outputs.count(), 2)
        self.assertEqual(len(report_content["agent_outputs_ref"]), 2)

        warning_blob = json.dumps(report_content["warnings"])
        for marker in PII_MARKERS:
            self.assertNotIn(marker, warning_blob)

        workflow_deps = self.coordinator_bridge.last_workflow_deps
        assert workflow_deps is not None
        self.assertFalse(
            any("/actions/" in entry["path"] for entry in workflow_deps.transport.request_log)
        )


class Phase10DbBackedE2EActionSafetyTests(LiveServerTestCase):
    """Prove coordinator workflow does not auto-approve or execute actions."""

    host = "127.0.0.1"
    @classmethod
    def setUpClass(cls):
        cls._env_patcher = patch.dict(
            os.environ,
            {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""},
            clear=False,
        )
        cls._env_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._env_patcher.stop()

    def setUp(self):
        self.api_client = APIClient()
        self.tenant = Tenant.objects.create(slug="tenant-c", name="Tenant C")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store C",
            slug="store-c",
            currency="USD",
        )
        self.manager = User.objects.create_user(
            email="manager-c@example.com",
            password="secure-pass-123",
            full_name="Manager C",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Clutch",
            slug="clutch",
            sku="CLUTCH-1",
            price=Decimal("40.00"),
        )
        self.pending_action = Action.objects.create(
            tenant=self.tenant,
            store=self.store,
            agent_name=AI_SERVICE_SALES,
            action_type=ACTION_TYPE_SALES_RESTOCK,
            title="Pending restock",
            description="Awaiting manager approval.",
            payload={"sku": "CLUTCH-1"},
            priority=1,
            requires_approval=True,
            status=ACTION_STATUS_PENDING_APPROVAL,
        )
        self.generate_url = reverse("api-reports-generate")
        self.coordinator_bridge = WorkflowCoordinatorBridgeServer(
            django_base_url=self.live_server_url,
            transport_factory=lambda: ServiceRouterTransport(),
        )
        self.coordinator_bridge.start()

    def tearDown(self):
        self.coordinator_bridge.stop()

    def test_coordinator_workflow_leaves_actions_pending_without_execution(self):
        with _integration_settings(
            self.live_server_url,
            self.coordinator_bridge.daily_report_url,
        ):
            self.api_client.force_authenticate(user=self.manager)
            response = self.api_client.post(self.generate_url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        new_report_run = ReportRun.objects.get(pk=response.data["report_run_id"])
        self.assertEqual(new_report_run.status, REPORT_RUN_STATUS_COMPLETED)

        self.pending_action.refresh_from_db()
        self.assertEqual(self.pending_action.status, ACTION_STATUS_PENDING_APPROVAL)
        self.assertIsNone(self.pending_action.decided_by_id)
        self.assertIsNone(self.pending_action.executed_at)

        self.assertEqual(Action.objects.filter(status=ACTION_STATUS_EXECUTED).count(), 0)
        self.assertEqual(Action.objects.filter(status=ACTION_STATUS_QUEUED).count(), 0)

        workflow_deps = self.coordinator_bridge.last_workflow_deps
        assert workflow_deps is not None
        action_paths = [
            entry["path"]
            for entry in workflow_deps.transport.request_log
            if "/actions/" in entry["path"]
        ]
        self.assertEqual(action_paths, [])
