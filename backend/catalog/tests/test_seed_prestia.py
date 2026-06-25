from django.core.management import call_command
from django.test import TestCase

from catalog.models import Category, Product
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
