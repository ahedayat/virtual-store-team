from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from stores.models import Store
from tenants.models import Tenant


class StoreDetailAPITests(APITestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.tenant_b = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.prestia_tenant = Tenant.objects.create(slug="prestia", name="Prestia")

        self.store_a = Store.objects.create(
            tenant=self.tenant_a,
            name="Store A",
            slug="main",
            timezone="America/New_York",
            currency="USD",
        )
        self.store_b = Store.objects.create(
            tenant=self.tenant_b,
            name="Store B",
            slug="main",
            timezone="Europe/London",
            currency="GBP",
        )
        self.prestia_store = Store.objects.create(
            tenant=self.prestia_tenant,
            name="Prestia Main",
            slug="main",
            timezone="Asia/Tehran",
            currency="IRR",
        )

        self.user_a = User.objects.create_user(
            email="user-a@example.com",
            password="secure-pass-123",
            tenant=self.tenant_a,
            store=self.store_a,
            role=UserRole.MANAGER,
        )
        self.user_b = User.objects.create_user(
            email="user-b@example.com",
            password="secure-pass-123",
            tenant=self.tenant_b,
            store=self.store_b,
            role=UserRole.MANAGER,
        )
        self.prestia_user = User.objects.create_user(
            email="manager@prestia.example",
            password="secure-pass-123",
            tenant=self.prestia_tenant,
            store=self.prestia_store,
            role=UserRole.MANAGER,
        )

    def _detail_url(self, store):
        return reverse("api-store-detail", kwargs={"store_id": store.pk})

    def test_authenticated_user_can_read_same_tenant_store(self):
        self.client.force_login(self.user_a)

        response = self.client.get(self._detail_url(self.store_a))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(self.store_a.pk))
        self.assertEqual(response.data["name"], "Store A")
        self.assertEqual(response.data["slug"], "main")
        self.assertEqual(response.data["timezone"], "America/New_York")
        self.assertEqual(response.data["currency"], "USD")
        self.assertEqual(str(response.data["tenant"]["id"]), str(self.tenant_a.pk))
        self.assertEqual(response.data["tenant"]["slug"], "tenant-a")
        self.assertNotIn("settings", response.data["tenant"])

    def test_authenticated_user_cannot_read_other_tenant_store_by_id(self):
        self.client.force_login(self.user_a)

        response = self.client.get(self._detail_url(self.store_b))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "Store not found.")

    def test_prestia_user_cannot_read_other_tenant_store_by_id(self):
        self.client.force_login(self.prestia_user)

        response = self.client.get(self._detail_url(self.store_b))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "Store not found.")

    def test_prestia_user_can_read_prestia_store(self):
        self.client.force_login(self.prestia_user)

        response = self.client.get(self._detail_url(self.prestia_store))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(self.prestia_store.pk))
        self.assertEqual(response.data["tenant"]["slug"], "prestia")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self._detail_url(self.store_a))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_response_does_not_leak_other_store_data(self):
        self.client.force_login(self.user_b)

        response = self.client.get(self._detail_url(self.store_a))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("name", response.data)
        self.assertNotIn("slug", response.data)
        self.assertNotIn("currency", response.data)
