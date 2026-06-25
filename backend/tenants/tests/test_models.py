from django.db import IntegrityError
from django.test import TestCase

from tenants.models import Tenant


class TenantModelTests(TestCase):
    def test_create_tenant_with_slug_name_and_default_settings(self):
        tenant = Tenant.objects.create(slug="acme", name="Acme Corp")

        self.assertEqual(tenant.slug, "acme")
        self.assertEqual(tenant.name, "Acme Corp")
        self.assertEqual(tenant.settings, {})

    def test_settings_defaults_to_empty_dict(self):
        tenant = Tenant(name="Defaults Inc", slug="defaults-inc")
        tenant.save()
        tenant.refresh_from_db()

        self.assertEqual(tenant.settings, {})

    def test_slug_uniqueness_is_enforced(self):
        Tenant.objects.create(slug="unique-slug", name="First Tenant")

        with self.assertRaises(IntegrityError):
            Tenant.objects.create(slug="unique-slug", name="Second Tenant")

    def test_str_returns_readable_name(self):
        tenant = Tenant(slug="readable", name="Readable Name")

        self.assertEqual(str(tenant), "Readable Name")
