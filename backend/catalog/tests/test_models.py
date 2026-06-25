from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from catalog.models import Category, InventoryLevel, Order, OrderItem, OrderStatus, Product
from stores.models import Store
from tenants.models import Tenant


class CategoryModelTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.store_b = Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="store-b",
            currency="EUR",
        )

    def test_create_category_for_tenant_store(self):
        category = Category.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Handbags",
            slug="handbags",
            description="Structured handbags.",
        )

        self.assertEqual(category.tenant_id, self.tenant_a.id)
        self.assertEqual(category.store_id, self.store_a.id)
        self.assertTrue(category.is_active)

    def test_category_slug_uniqueness_within_tenant_store(self):
        Category.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="First Category",
            slug="shared-slug",
        )

        with self.assertRaises(IntegrityError):
            Category.objects.create(
                tenant=self.tenant_a,
                store=self.store_a,
                name="Second Category",
                slug="shared-slug",
            )

    def test_same_category_slug_allowed_across_stores(self):
        store_a2 = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A2",
            slug="store-a2",
            currency="USD",
        )
        Category.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Handbags",
            slug="handbags",
        )
        category = Category.objects.create(
            tenant=self.tenant_a,
            store=store_a2,
            name="Handbags",
            slug="handbags",
        )

        self.assertEqual(category.slug, "handbags")


class ProductModelTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.store_b = Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="store-b",
            currency="EUR",
        )
        self.category_a = Category.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Handbags",
            slug="handbags",
        )

    def test_create_product_for_tenant_store(self):
        product = Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            category=self.category_a,
            name="Leather Tote",
            slug="leather-tote",
            sku="SKU-001",
            description="A classic leather tote.",
            price=Decimal("189.00"),
        )

        self.assertEqual(product.tenant_id, self.tenant_a.id)
        self.assertEqual(product.store_id, self.store_a.id)
        self.assertEqual(product.category_id, self.category_a.id)
        self.assertTrue(product.is_active)

    def test_product_sku_uniqueness_within_tenant_store(self):
        Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="First Product",
            slug="first-product",
            sku="SHARED-SKU",
            price=Decimal("10.00"),
        )

        with self.assertRaises(IntegrityError):
            Product.objects.create(
                tenant=self.tenant_a,
                store=self.store_a,
                name="Second Product",
                slug="second-product",
                sku="SHARED-SKU",
                price=Decimal("20.00"),
            )

    def test_same_product_sku_allowed_across_stores(self):
        store_a2 = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A2",
            slug="store-a2",
            currency="USD",
        )
        Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Shared SKU Product",
            slug="shared-sku-product-a",
            sku="SHARED-SKU",
            price=Decimal("10.00"),
        )
        product = Product.objects.create(
            tenant=self.tenant_a,
            store=store_a2,
            name="Shared SKU Product",
            slug="shared-sku-product-b",
            sku="SHARED-SKU",
            price=Decimal("10.00"),
        )

        self.assertEqual(product.sku, "SHARED-SKU")

    def test_product_slug_uniqueness_within_tenant_store(self):
        Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="First Product",
            slug="shared-slug",
            sku="SKU-A",
            price=Decimal("10.00"),
        )

        with self.assertRaises(IntegrityError):
            Product.objects.create(
                tenant=self.tenant_a,
                store=self.store_a,
                name="Second Product",
                slug="shared-slug",
                sku="SKU-B",
                price=Decimal("20.00"),
            )

    def test_same_product_slug_allowed_across_stores(self):
        store_a2 = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A2",
            slug="store-a2",
            currency="USD",
        )
        Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Shared Slug Product",
            slug="shared-slug",
            sku="SKU-A",
            price=Decimal("10.00"),
        )
        product = Product.objects.create(
            tenant=self.tenant_a,
            store=store_a2,
            name="Shared Slug Product",
            slug="shared-slug",
            sku="SKU-B",
            price=Decimal("10.00"),
        )

        self.assertEqual(product.slug, "shared-slug")


class OrderModelTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.product = Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Leather Tote",
            slug="leather-tote",
            sku="SKU-001",
            price=Decimal("100.00"),
        )

    def test_create_order_and_order_item_for_tenant_store(self):
        order = Order.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            order_number="ORD-001",
            status=OrderStatus.PAID,
            currency="USD",
            subtotal_amount=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
        )
        item = OrderItem.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            sku_snapshot=self.product.sku,
            quantity=1,
            unit_price=Decimal("100.00"),
            line_total=Decimal("100.00"),
        )

        self.assertEqual(order.tenant_id, self.tenant_a.id)
        self.assertEqual(order.store_id, self.store_a.id)
        self.assertEqual(item.order_id, order.id)
        self.assertEqual(item.product_id, self.product.id)

    def test_order_number_uniqueness_within_tenant_store(self):
        Order.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            order_number="SHARED-ORD",
            status=OrderStatus.PAID,
            currency="USD",
            subtotal_amount=Decimal("10.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("10.00"),
        )

        with self.assertRaises(IntegrityError):
            Order.objects.create(
                tenant=self.tenant_a,
                store=self.store_a,
                order_number="SHARED-ORD",
                status=OrderStatus.PAID,
                currency="USD",
                subtotal_amount=Decimal("20.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("20.00"),
            )


class InventoryLevelModelTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="store-a",
            currency="USD",
        )
        self.product = Product.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            name="Leather Tote",
            slug="leather-tote",
            sku="SKU-001",
            price=Decimal("100.00"),
        )

    def test_create_inventory_level_for_tenant_store(self):
        inventory = InventoryLevel.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            product=self.product,
            quantity_on_hand=20,
            reserved_quantity=5,
            low_stock_threshold=10,
            reorder_target=40,
        )

        self.assertEqual(inventory.tenant_id, self.tenant_a.id)
        self.assertEqual(inventory.store_id, self.store_a.id)
        self.assertEqual(inventory.product_id, self.product.id)
        self.assertTrue(inventory.is_active)

    def test_available_quantity_is_calculated_correctly(self):
        inventory = InventoryLevel.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            product=self.product,
            quantity_on_hand=20,
            reserved_quantity=5,
            low_stock_threshold=10,
        )

        self.assertEqual(inventory.available_quantity, 15)

    def test_inventory_unique_per_product_per_store(self):
        InventoryLevel.objects.create(
            tenant=self.tenant_a,
            store=self.store_a,
            product=self.product,
            quantity_on_hand=10,
            low_stock_threshold=5,
        )

        with self.assertRaises(IntegrityError):
            InventoryLevel.objects.create(
                tenant=self.tenant_a,
                store=self.store_a,
                product=self.product,
                quantity_on_hand=5,
                low_stock_threshold=3,
            )
