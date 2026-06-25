from django.db import IntegrityError
from django.test import TestCase

from stores.models import Store
from tenants.models import Tenant


class StoreModelTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")

    def test_create_store_for_tenant(self):
        store = Store.objects.create(
            tenant=self.tenant_a,
            name="Main Store",
            slug="main",
            timezone="America/New_York",
            currency="USD",
        )

        self.assertEqual(store.name, "Main Store")
        self.assertEqual(store.slug, "main")

    def test_store_is_linked_to_correct_tenant(self):
        store = Store.objects.create(
            tenant=self.tenant_a,
            name="Linked Store",
            slug="linked",
            currency="EUR",
        )

        self.assertEqual(store.tenant_id, self.tenant_a.id)
        self.assertEqual(list(self.tenant_a.stores.all()), [store])

    def test_tenant_slug_uniqueness_is_enforced(self):
        Store.objects.create(
            tenant=self.tenant_a,
            name="First Store",
            slug="shared-slug",
            currency="USD",
        )

        with self.assertRaises(IntegrityError):
            Store.objects.create(
                tenant=self.tenant_a,
                name="Second Store",
                slug="shared-slug",
                currency="USD",
            )

    def test_same_slug_can_be_used_under_different_tenants(self):
        store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="shared-slug",
            currency="USD",
        )
        store_b = Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="shared-slug",
            currency="GBP",
        )

        self.assertEqual(store_a.slug, store_b.slug)
        self.assertNotEqual(store_a.tenant_id, store_b.tenant_id)

    def test_timezone_and_currency_values_are_stored_correctly(self):
        store = Store.objects.create(
            tenant=self.tenant_a,
            name="Regional Store",
            slug="regional",
            timezone="Europe/London",
            currency="GBP",
        )
        store.refresh_from_db()

        self.assertEqual(store.timezone, "Europe/London")
        self.assertEqual(store.currency, "GBP")

    def test_timezone_defaults_to_utc(self):
        store = Store.objects.create(
            tenant=self.tenant_a,
            name="Default Timezone Store",
            slug="default-tz",
            currency="USD",
        )
        store.refresh_from_db()

        self.assertEqual(store.timezone, "UTC")

    def test_str_returns_readable_value(self):
        store = Store(
            tenant=self.tenant_a,
            name="Readable Store",
            slug="readable",
            currency="USD",
        )

        self.assertEqual(str(store), "Readable Store (Tenant A)")
