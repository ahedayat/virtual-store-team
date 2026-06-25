from django.core.management import call_command
from django.test import TestCase

from catalog.models import (
    Category,
    Customer,
    InventoryLevel,
    Message,
    MessageThread,
    Order,
    OrderItem,
    Product,
)
from stores.models import Store
from tenants.models import Tenant


class SeedPrestiaCommandTests(TestCase):
    def test_seed_prestia_creates_categories_and_products(self):
        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")

        self.assertEqual(Category.objects.filter(tenant=tenant, store=store).count(), 5)
        self.assertEqual(Product.objects.filter(tenant=tenant, store=store).count(), 10)

        handbags = Category.objects.get(tenant=tenant, store=store, slug="handbags")
        product = Product.objects.get(tenant=tenant, store=store, sku="PRS-TOTE-001")
        self.assertEqual(product.category_id, handbags.id)
        self.assertTrue(product.is_active)

    def test_seed_prestia_is_idempotent(self):
        call_command("seed_prestia")
        category_count = Category.objects.count()
        product_count = Product.objects.count()
        tenant_count = Tenant.objects.filter(slug="prestia").count()
        store_count = Store.objects.filter(slug="main").count()

        call_command("seed_prestia")

        self.assertEqual(Tenant.objects.filter(slug="prestia").count(), tenant_count)
        self.assertEqual(Store.objects.filter(slug="main").count(), store_count)
        self.assertEqual(Category.objects.count(), category_count)
        self.assertEqual(Product.objects.count(), product_count)

    def test_seed_prestia_creates_orders_and_order_items(self):
        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")
        orders = Order.objects.filter(tenant=tenant, store=store)

        self.assertGreaterEqual(orders.count(), 7)
        self.assertGreaterEqual(
            OrderItem.objects.filter(tenant=tenant, store=store).count(),
            10,
        )
        self.assertTrue(orders.filter(status="cancelled").exists())
        self.assertTrue(orders.filter(status="draft").exists())

    def test_seed_prestia_orders_are_idempotent(self):
        call_command("seed_prestia")
        order_count = Order.objects.count()
        order_item_count = OrderItem.objects.count()

        call_command("seed_prestia")

        self.assertEqual(Order.objects.count(), order_count)
        self.assertEqual(OrderItem.objects.count(), order_item_count)

    def test_seed_prestia_creates_inventory_levels(self):
        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")

        self.assertEqual(
            InventoryLevel.objects.filter(tenant=tenant, store=store).count(),
            10,
        )
        tote = InventoryLevel.objects.get(
            tenant=tenant,
            store=store,
            product__sku="PRS-TOTE-001",
        )
        self.assertEqual(tote.available_quantity, 3)
        self.assertEqual(tote.low_stock_threshold, 10)

    def test_seed_prestia_inventory_is_idempotent(self):
        call_command("seed_prestia")
        inventory_count = InventoryLevel.objects.count()

        call_command("seed_prestia")

        self.assertEqual(InventoryLevel.objects.count(), inventory_count)

    def test_seed_prestia_creates_customers_threads_and_messages(self):
        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")

        self.assertEqual(Customer.objects.filter(tenant=tenant, store=store).count(), 5)
        self.assertEqual(
            MessageThread.objects.filter(tenant=tenant, store=store).count(),
            5,
        )
        self.assertGreaterEqual(
            Message.objects.filter(tenant=tenant, store=store).count(),
            10,
        )
        self.assertTrue(
            Message.objects.filter(
                tenant=tenant,
                store=store,
                body__icontains="sara.jamali@example.com",
            ).exists()
        )
        self.assertTrue(
            Message.objects.filter(
                tenant=tenant,
                store=store,
                body__icontains="۰۹۱۷۱۱۲۲۳۳۴",
            ).exists()
        )

    def test_seed_prestia_messages_are_idempotent(self):
        call_command("seed_prestia")
        customer_count = Customer.objects.count()
        thread_count = MessageThread.objects.count()
        message_count = Message.objects.count()

        call_command("seed_prestia")

        self.assertEqual(Customer.objects.count(), customer_count)
        self.assertEqual(MessageThread.objects.count(), thread_count)
        self.assertEqual(Message.objects.count(), message_count)
