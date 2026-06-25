import json
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.service_jwt import mint_service_jwt
from catalog.models import InventoryLevel, Product
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}

PII_FIELD_NAMES = {
    "customer_name",
    "customer_email",
    "email",
    "phone",
    "phone_number",
    "address",
    "instagram",
    "instagram_handle",
    "external_customer_ref",
}


@override_settings(**TEST_JWT_SETTINGS)
class InternalLowStockInventoryAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="tenant-a", name="Tenant A")
        self.other_tenant = Tenant.objects.create(slug="tenant-b", name="Tenant B")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Store A",
            slug="store-a",
            currency="USD",
            timezone="America/New_York",
        )
        self.other_store = Store.objects.create(
            tenant=self.tenant,
            name="Store B",
            slug="store-b",
            currency="USD",
            timezone="America/New_York",
        )
        self.foreign_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Foreign Store",
            slug="foreign",
            currency="EUR",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            store=self.store,
            name="Leather Tote",
            slug="leather-tote",
            sku="SKU-A",
            price=Decimal("100.00"),
        )
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)
        self.low_stock_url = reverse(
            "internal-ai-low-stock-inventory",
            kwargs={"store_id": self.store.id},
        )

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_SALES),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _seed_low_stock_inventory(self):
        InventoryLevel.objects.create(
            tenant=self.tenant,
            store=self.store,
            product=self.product,
            quantity_on_hand=3,
            reserved_quantity=1,
            low_stock_threshold=10,
            reorder_target=25,
        )

    def test_low_stock_requires_service_jwt(self):
        response = self.client.get(self.low_stock_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_low_stock_accepts_valid_service_jwt(self):
        self._seed_low_stock_inventory()
        token = self._mint_token()

        response = self.client.get(self.low_stock_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["store_id"], self.store_id)
        self.assertEqual(response.data["low_stock_count"], 1)
        self.assertEqual(response.data["items"][0]["sku"], "SKU-A")
        self.assertEqual(response.data["items"][0]["available_quantity"], 2)

    def test_low_stock_rejects_cross_store_access(self):
        token = self._mint_token(store_id=str(self.other_store.id))

        response = self.client.get(self.low_stock_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_low_stock_rejects_cross_tenant_store_access(self):
        token = self._mint_token()
        url = reverse(
            "internal-ai-low-stock-inventory",
            kwargs={"store_id": self.foreign_store.id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_low_stock_returns_not_found_for_missing_store(self):
        missing_store_id = "00000000-0000-0000-0000-000000000099"
        token = self._mint_token(store_id=missing_store_id)
        url = reverse(
            "internal-ai-low-stock-inventory",
            kwargs={"store_id": missing_store_id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_low_stock_response_does_not_contain_raw_customer_pii(self):
        self._seed_low_stock_inventory()
        token = self._mint_token()

        response = self.client.get(self.low_stock_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = json.dumps(response.data, default=str).lower()
        for field_name in PII_FIELD_NAMES:
            self.assertNotIn(field_name, payload)
