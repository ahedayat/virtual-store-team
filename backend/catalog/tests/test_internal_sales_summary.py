import json
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SALES
from accounts.service_jwt import mint_service_jwt
from catalog.models import Order, OrderItem, OrderStatus, Product
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
class InternalSalesSummaryAPITests(APITestCase):
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
        self.summary_url = reverse(
            "internal-ai-sales-summary",
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

    def _seed_paid_order(self):
        placed_at = timezone.now().astimezone(ZoneInfo("America/New_York")).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number="ORD-API-1",
            status=OrderStatus.PAID,
            currency="USD",
            subtotal_amount=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            placed_at=placed_at,
            external_customer_ref="opaque-ref-should-not-appear",
        )
        OrderItem.objects.create(
            tenant=self.tenant,
            store=self.store,
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            sku_snapshot=self.product.sku,
            quantity=1,
            unit_price=Decimal("100.00"),
            line_total=Decimal("100.00"),
        )

    def test_sales_summary_requires_service_jwt(self):
        response = self.client.get(self.summary_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sales_summary_accepts_valid_service_jwt(self):
        self._seed_paid_order()
        token = self._mint_token()

        response = self.client.get(self.summary_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["store_id"], self.store_id)
        self.assertEqual(response.data["currency"], "USD")
        self.assertIn("periods", response.data)
        self.assertGreaterEqual(response.data["periods"]["today"]["order_count"], 1)

    def test_sales_summary_rejects_cross_store_access(self):
        token = self._mint_token(store_id=str(self.other_store.id))
        url = reverse(
            "internal-ai-sales-summary",
            kwargs={"store_id": self.store.id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_summary_rejects_cross_tenant_store_access(self):
        token = self._mint_token()
        url = reverse(
            "internal-ai-sales-summary",
            kwargs={"store_id": self.foreign_store.id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_summary_returns_not_found_for_missing_store(self):
        missing_store_id = "00000000-0000-0000-0000-000000000099"
        token = self._mint_token(store_id=missing_store_id)
        url = reverse(
            "internal-ai-sales-summary",
            kwargs={"store_id": missing_store_id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sales_summary_response_does_not_contain_raw_customer_pii(self):
        self._seed_paid_order()
        token = self._mint_token()

        response = self.client.get(self.summary_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = json.dumps(response.data, default=str).lower()
        for field_name in PII_FIELD_NAMES:
            self.assertNotIn(field_name, payload)
