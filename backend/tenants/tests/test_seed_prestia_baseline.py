from django.core.management import call_command
from django.test import TestCase

from stores.models import Store
from tenants.models import Tenant


class SeedPrestiaPhase1BaselineTests(TestCase):
    """Phase 1.7: tenant/store baseline only — not catalog/demo data."""

    def test_seed_prestia_creates_prestia_tenant_when_missing(self):
        self.assertFalse(Tenant.objects.filter(slug="prestia").exists())

        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        self.assertEqual(tenant.name, "Prestia")
        self.assertEqual(tenant.settings, {"store_display_name": "Prestia"})

    def test_seed_prestia_creates_main_prestia_store_when_missing(self):
        self.assertFalse(Store.objects.filter(slug="main").exists())

        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")
        self.assertEqual(store.name, "Prestia Online Store")
        self.assertEqual(store.timezone, "America/New_York")
        self.assertEqual(store.currency, "USD")

    def test_seed_prestia_does_not_create_duplicate_tenants(self):
        call_command("seed_prestia")
        tenant_id = Tenant.objects.get(slug="prestia").id

        call_command("seed_prestia")

        self.assertEqual(Tenant.objects.filter(slug="prestia").count(), 1)
        self.assertEqual(Tenant.objects.get(slug="prestia").id, tenant_id)

    def test_seed_prestia_does_not_create_duplicate_main_stores(self):
        call_command("seed_prestia")
        tenant = Tenant.objects.get(slug="prestia")
        store_id = Store.objects.get(tenant=tenant, slug="main").id

        call_command("seed_prestia")

        self.assertEqual(Store.objects.filter(tenant=tenant, slug="main").count(), 1)
        self.assertEqual(Store.objects.get(tenant=tenant, slug="main").id, store_id)

    def test_phase1_baseline_does_not_require_catalog_data(self):
        call_command("seed_prestia")

        tenant = Tenant.objects.get(slug="prestia")
        store = Store.objects.get(tenant=tenant, slug="main")

        self.assertIsNotNone(tenant.id)
        self.assertIsNotNone(store.id)
        self.assertEqual(store.tenant_id, tenant.id)
