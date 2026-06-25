from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from stores.models import Store
from tenants.middleware import ACTIVE_TENANT_ID_SESSION_KEY, TenantMiddleware
from tenants.models import Tenant


class StoreTenantIsolationTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")

        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="main",
            currency="USD",
        )
        self.store_b = Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="main",
            currency="GBP",
        )

    def test_for_tenant_includes_only_matching_tenant_stores(self):
        stores = Store.objects.for_tenant(self.tenant_a)

        self.assertEqual(list(stores), [self.store_a])

    def test_for_tenant_excludes_other_tenant_stores(self):
        stores = Store.objects.for_tenant(self.tenant_a)

        self.assertNotIn(self.store_b, stores)

    def test_get_for_tenant_denies_cross_tenant_access_by_id(self):
        with self.assertRaises(Store.DoesNotExist):
            Store.objects.get_for_tenant(self.tenant_a, pk=self.store_b.pk)

    def test_get_for_tenant_denies_cross_tenant_access_by_slug(self):
        other_store = Store.objects.create(
            tenant=self.tenant_b,
            name="Tenant B Only",
            slug="tenant-b-only",
            currency="EUR",
        )

        with self.assertRaises(Store.DoesNotExist):
            Store.objects.get_for_tenant(self.tenant_a, slug=other_store.slug)

    def test_get_for_tenant_returns_store_within_tenant(self):
        store = Store.objects.get_for_tenant(self.tenant_a, pk=self.store_a.pk)

        self.assertEqual(store, self.store_a)

    def test_for_tenant_with_none_returns_empty_queryset(self):
        self.assertEqual(list(Store.objects.for_tenant(None)), [])

    def test_get_for_tenant_with_none_raises_does_not_exist(self):
        with self.assertRaises(Store.DoesNotExist):
            Store.objects.get_for_tenant(None, pk=self.store_a.pk)

    def test_same_slug_can_exist_under_different_tenants_with_scoped_access(self):
        store_a = Store.objects.get_for_tenant(self.tenant_a, slug="main")
        store_b = Store.objects.get_for_tenant(self.tenant_b, slug="main")

        self.assertEqual(store_a.slug, store_b.slug)
        self.assertNotEqual(store_a.pk, store_b.pk)

    def test_unscoped_manager_still_returns_all_stores(self):
        store_ids = set(Store.objects.values_list("pk", flat=True))

        self.assertEqual(store_ids, {self.store_a.pk, self.store_b.pk})


class StoreRequestTenantIntegrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda request: HttpResponse("ok"))

        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")

        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="main",
            currency="USD",
        )
        Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="main",
            currency="GBP",
        )

    def _process_request_with_session_tenant(self, tenant):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session[ACTIVE_TENANT_ID_SESSION_KEY] = str(tenant.id)
        request.session.save()
        self.middleware(request)
        return request

    def test_for_request_uses_middleware_tenant_context(self):
        request = self._process_request_with_session_tenant(self.tenant_a)

        stores = Store.objects.for_request(request)

        self.assertEqual(list(stores), [self.store_a])

    def test_for_request_excludes_other_tenant_stores(self):
        request = self._process_request_with_session_tenant(self.tenant_a)

        store_ids = set(Store.objects.for_request(request).values_list("pk", flat=True))

        self.assertEqual(store_ids, {self.store_a.pk})

    def test_for_request_with_no_tenant_returns_empty_queryset(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()
        self.middleware(request)

        self.assertEqual(list(Store.objects.for_request(request)), [])
