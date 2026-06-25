from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase

from catalog.models import (
    Category,
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
    ThreadStatus,
)
from catalog.services import (
    build_low_stock_summary,
    build_recent_messages_summary,
    build_sales_summary,
    get_period_bounds,
)
from stores.models import Store
from tenants.models import Tenant


class SalesAggregationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
            timezone="America/New_York",
        )
        self.product_a = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Leather Tote",
            slug="leather-tote",
            sku="SKU-A",
            price=Decimal("100.00"),
        )
        self.product_b = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Mini Crossbody",
            slug="mini-crossbody",
            sku="SKU-B",
            price=Decimal("50.00"),
        )
        self.reference = datetime(2026, 6, 25, 18, 0, tzinfo=ZoneInfo("UTC"))

    def _create_order(self, *, order_number, status, placed_at, items):
        subtotal = sum(
            (item["unit_price"] * item["quantity"] for item in items),
            Decimal("0.00"),
        )
        order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number=order_number,
            status=status,
            currency="USD",
            subtotal_amount=subtotal,
            discount_amount=Decimal("0.00"),
            total_amount=subtotal,
            placed_at=placed_at,
        )
        for item in items:
            OrderItem.objects.create(
                tenant=self.tenant,
                store=self.store,
                order=order,
                product=item["product"],
                product_name_snapshot=item["product"].name,
                sku_snapshot=item["product"].sku,
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_total=item["unit_price"] * item["quantity"],
            )
        return order

    def test_today_summary_calculates_metrics(self):
        bounds = get_period_bounds(self.store, reference=self.reference)
        today_midday = bounds["today"].start + timedelta(hours=12)

        self._create_order(
            order_number="ORD-TODAY-1",
            status=OrderStatus.PAID,
            placed_at=today_midday,
            items=[
                {"product": self.product_a, "quantity": 2, "unit_price": Decimal("100.00")},
                {"product": self.product_b, "quantity": 1, "unit_price": Decimal("50.00")},
            ],
        )
        self._create_order(
            order_number="ORD-TODAY-2",
            status=OrderStatus.COMPLETED,
            placed_at=today_midday + timedelta(hours=1),
            items=[
                {"product": self.product_b, "quantity": 3, "unit_price": Decimal("50.00")},
            ],
        )

        summary = build_sales_summary(self.store, reference=self.reference)
        today = summary["periods"]["today"]

        self.assertEqual(today["order_count"], 2)
        self.assertEqual(today["total_revenue"], Decimal("400.00"))
        self.assertEqual(today["units_sold"], 6)
        self.assertEqual(today["average_order_value"], Decimal("200.00"))
        self.assertEqual(len(today["top_products"]), 2)
        top_by_sku = {row["sku"]: row for row in today["top_products"]}
        self.assertEqual(top_by_sku["SKU-A"]["quantity_sold"], 2)
        self.assertEqual(top_by_sku["SKU-A"]["revenue"], Decimal("200.00"))
        self.assertEqual(top_by_sku["SKU-B"]["quantity_sold"], 4)
        self.assertEqual(top_by_sku["SKU-B"]["revenue"], Decimal("200.00"))

    def test_last_7_days_summary_includes_older_orders(self):
        bounds = get_period_bounds(self.store, reference=self.reference)
        six_days_ago = bounds["last_7_days"].start + timedelta(hours=10)

        self._create_order(
            order_number="ORD-WEEK-1",
            status=OrderStatus.FULFILLED,
            placed_at=six_days_ago,
            items=[
                {"product": self.product_a, "quantity": 1, "unit_price": Decimal("100.00")},
            ],
        )

        summary = build_sales_summary(self.store, reference=self.reference)
        last_7_days = summary["periods"]["last_7_days"]

        self.assertEqual(last_7_days["order_count"], 1)
        self.assertEqual(last_7_days["total_revenue"], Decimal("100.00"))
        self.assertEqual(last_7_days["units_sold"], 1)

    def test_non_countable_statuses_are_excluded_from_revenue(self):
        bounds = get_period_bounds(self.store, reference=self.reference)
        today_midday = bounds["today"].start + timedelta(hours=12)

        self._create_order(
            order_number="ORD-CANCELLED",
            status=OrderStatus.CANCELLED,
            placed_at=today_midday,
            items=[
                {"product": self.product_a, "quantity": 5, "unit_price": Decimal("100.00")},
            ],
        )
        self._create_order(
            order_number="ORD-DRAFT",
            status=OrderStatus.DRAFT,
            placed_at=today_midday,
            items=[
                {"product": self.product_b, "quantity": 2, "unit_price": Decimal("50.00")},
            ],
        )
        self._create_order(
            order_number="ORD-PAID",
            status=OrderStatus.PAID,
            placed_at=today_midday,
            items=[
                {"product": self.product_b, "quantity": 1, "unit_price": Decimal("50.00")},
            ],
        )

        summary = build_sales_summary(self.store, reference=self.reference)
        today = summary["periods"]["today"]

        self.assertEqual(today["order_count"], 1)
        self.assertEqual(today["total_revenue"], Decimal("50.00"))
        self.assertEqual(today["units_sold"], 1)

    def test_summary_includes_generated_at_store_id_and_currency(self):
        summary = build_sales_summary(self.store, reference=self.reference)

        self.assertEqual(summary["store_id"], str(self.store.id))
        self.assertEqual(summary["currency"], "USD")
        self.assertEqual(summary["generated_at"], self.reference.isoformat())
        self.assertIn("today", summary["periods"])
        self.assertIn("last_7_days", summary["periods"])


class LowStockInventoryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.category = Category.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Handbags",
            slug="handbags",
        )
        self.product_below = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            category=self.category,
            name="Below Threshold",
            slug="below-threshold",
            sku="SKU-LOW",
            price=Decimal("50.00"),
        )
        self.product_at = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="At Threshold",
            slug="at-threshold",
            sku="SKU-AT",
            price=Decimal("50.00"),
        )
        self.product_above = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Above Threshold",
            slug="above-threshold",
            sku="SKU-HIGH",
            price=Decimal("50.00"),
        )
        self.product_inactive = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Inactive Product",
            slug="inactive-product",
            sku="SKU-INACTIVE",
            price=Decimal("50.00"),
            is_active=False,
        )

    def _create_inventory(self, product, **kwargs):
        defaults = {
            "tenant": self.tenant,
            "store": self.store,
            "quantity_on_hand": 10,
            "reserved_quantity": 0,
            "low_stock_threshold": 10,
            "is_active": True,
        }
        defaults.update(kwargs)
        return InventoryLevel.objects.create(product=product, **defaults)

    def test_low_stock_returns_only_products_below_threshold(self):
        self._create_inventory(
            self.product_below,
            quantity_on_hand=5,
            reserved_quantity=1,
            low_stock_threshold=10,
            reorder_target=20,
        )
        self._create_inventory(
            self.product_at,
            quantity_on_hand=10,
            reserved_quantity=0,
            low_stock_threshold=10,
        )
        self._create_inventory(
            self.product_above,
            quantity_on_hand=25,
            reserved_quantity=0,
            low_stock_threshold=10,
        )

        summary = build_low_stock_summary(self.store)
        skus = {item["sku"] for item in summary["items"]}

        self.assertEqual(summary["low_stock_count"], 1)
        self.assertEqual(skus, {"SKU-LOW"})
        item = summary["items"][0]
        self.assertEqual(item["available_quantity"], 4)
        self.assertEqual(item["shortage_units"], 6)
        self.assertEqual(item["suggested_reorder_quantity"], 16)

    def test_product_exactly_at_threshold_is_not_returned(self):
        self._create_inventory(
            self.product_at,
            quantity_on_hand=10,
            reserved_quantity=0,
            low_stock_threshold=10,
        )

        summary = build_low_stock_summary(self.store)

        self.assertEqual(summary["low_stock_count"], 0)
        self.assertEqual(summary["items"], [])

    def test_product_above_threshold_is_not_returned(self):
        self._create_inventory(
            self.product_above,
            quantity_on_hand=30,
            reserved_quantity=5,
            low_stock_threshold=10,
        )

        summary = build_low_stock_summary(self.store)

        self.assertEqual(summary["low_stock_count"], 0)

    def test_inactive_inventory_records_are_excluded(self):
        self._create_inventory(
            self.product_below,
            quantity_on_hand=2,
            low_stock_threshold=10,
            is_active=False,
        )

        summary = build_low_stock_summary(self.store)

        self.assertEqual(summary["low_stock_count"], 0)

    def test_inactive_products_are_excluded(self):
        self._create_inventory(
            self.product_inactive,
            quantity_on_hand=1,
            low_stock_threshold=10,
        )

        summary = build_low_stock_summary(self.store)

        self.assertEqual(summary["low_stock_count"], 0)


class RecentMessagesSummaryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
            timezone="America/New_York",
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            store=self.store,
            display_name="Sara Jamali",
            email="sara@example.com",
            phone="09121234567",
            platform=Platform.INSTAGRAM,
            platform_user_id="ig-001",
        )

    def _create_thread_with_message(self, *, external_thread_id, subject, sent_at, body):
        thread = MessageThread.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer=self.customer,
            platform=Platform.INSTAGRAM,
            external_thread_id=external_thread_id,
            subject=subject,
            last_message_at=sent_at,
        )
        Message.objects.create(
            tenant=self.tenant,
            store=self.store,
            thread=thread,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            body=body,
            external_message_id=f"msg-{external_thread_id}",
            sent_at=sent_at,
        )
        return thread

    def test_recent_messages_ordered_by_last_message_at(self):
        older = datetime(2026, 6, 20, 10, 0, tzinfo=ZoneInfo("UTC"))
        newer = datetime(2026, 6, 25, 15, 0, tzinfo=ZoneInfo("UTC"))

        self._create_thread_with_message(
            external_thread_id="thread-old",
            subject="Older thread",
            sent_at=older,
            body="Old question",
        )
        self._create_thread_with_message(
            external_thread_id="thread-new",
            subject="Newer thread",
            sent_at=newer,
            body="New question",
        )

        summary = build_recent_messages_summary(self.store, thread_limit=10)
        thread_ids = [thread["thread_id"] for thread in summary["threads"]]

        self.assertEqual(len(thread_ids), 2)
        self.assertEqual(summary["threads"][0]["subject"], "Newer thread")
        self.assertEqual(summary["threads"][1]["subject"], "Older thread")

    def test_recent_messages_sanitize_body_and_exclude_raw_pii_fields(self):
        sent_at = datetime(2026, 6, 25, 12, 0, tzinfo=ZoneInfo("UTC"))
        self._create_thread_with_message(
            external_thread_id="thread-pii",
            subject="Contact request",
            sent_at=sent_at,
            body="Email me at sara@example.com or call 09121234567",
        )

        summary = build_recent_messages_summary(self.store)
        thread = summary["threads"][0]
        body = thread["messages"][0]["body"]

        self.assertEqual(thread["customer_ref"], f"customer-{self.customer.id}")
        self.assertNotIn("sara@example.com", body)
        self.assertNotIn("09121234567", body)
        self.assertNotIn("display_name", thread)
        self.assertNotIn("email", thread)
        self.assertNotIn("phone", thread)
