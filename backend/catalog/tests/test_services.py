from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase

from catalog.models import Order, OrderItem, OrderStatus, Product
from catalog.services import build_sales_summary, get_period_bounds
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
