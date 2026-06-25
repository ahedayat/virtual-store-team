import json
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR
from accounts.service_jwt import mint_service_jwt
from catalog.models import (
    Customer,
    InventoryLevel,
    Message,
    MessageDirection,
    MessageThread,
    Order,
    OrderItem,
    OrderStatus,
    Platform,
    Product,
    SenderType,
)
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
    "instagram_handle",
    "external_customer_ref",
    "display_name",
    "platform_user_id",
}

RAW_PII_VALUES = {
    "sara.jamali@example.com",
    "09121234567",
    "۰۹۱۷۱۱۲۲۳۳۴",
    "+98 912 555 0199",
}

TOP_LEVEL_KEYS = {
    "report_run_id",
    "generated_at",
    "tenant",
    "store",
    "products",
    "sales_summary",
    "inventory",
    "messages",
    "warnings",
}


@override_settings(**TEST_JWT_SETTINGS)
class InternalContextBundleAPITests(APITestCase):
    def setUp(self):
        self.report_run_id = uuid.uuid4()
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
        self.other_store_product = Product.objects.create(
            tenant=self.tenant,
            store=self.other_store,
            name="Other Store Bag",
            slug="other-store-bag",
            sku="SKU-OTHER",
            price=Decimal("50.00"),
        )
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)
        self.context_url = reverse(
            "internal-ai-context",
            kwargs={"report_run_id": self.report_run_id},
        )

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_COORDINATOR),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
            report_run_id=kwargs.get("report_run_id"),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _seed_full_store_data(self):
        placed_at = timezone.now().astimezone(ZoneInfo("America/New_York")).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        order = Order.objects.create(
            tenant=self.tenant,
            store=self.store,
            order_number="ORD-CTX-1",
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
        InventoryLevel.objects.create(
            tenant=self.tenant,
            store=self.store,
            product=self.product,
            quantity_on_hand=3,
            reserved_quantity=1,
            low_stock_threshold=10,
            reorder_target=25,
        )
        customer = Customer.objects.create(
            tenant=self.tenant,
            store=self.store,
            display_name="Sara Jamali",
            email="sara.jamali@example.com",
            phone="09121234567",
            platform=Platform.INSTAGRAM,
            platform_user_id="ig-test-001",
        )
        sent_at = datetime(2026, 6, 25, 12, 0, tzinfo=ZoneInfo("UTC"))
        thread = MessageThread.objects.create(
            tenant=self.tenant,
            store=self.store,
            customer=customer,
            platform=Platform.INSTAGRAM,
            external_thread_id="thread-test-001",
            subject="Availability question",
            last_message_at=sent_at,
        )
        Message.objects.create(
            tenant=self.tenant,
            store=self.store,
            thread=thread,
            direction=MessageDirection.INBOUND,
            sender_type=SenderType.CUSTOMER,
            body=(
                "Please email sara.jamali@example.com or call 09121234567 about the tote."
            ),
            external_message_id="msg-test-001",
            sent_at=sent_at,
        )

    def _model_counts(self):
        counts = {}
        for model in apps.get_app_config("catalog").get_models():
            counts[model._meta.label] = model.objects.count()
        counts["tenants.Tenant"] = Tenant.objects.count()
        counts["stores.Store"] = Store.objects.count()
        return counts

    def test_context_requires_service_jwt(self):
        response = self.client.get(self.context_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_context_accepts_valid_service_jwt(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["report_run_id"], str(self.report_run_id))
        self.assertEqual(response.data["tenant"]["id"], self.tenant_id)
        self.assertEqual(response.data["store"]["id"], self.store_id)

    def test_context_rejects_cross_tenant_access(self):
        token = self._mint_token(store_id=str(self.foreign_store.id))

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_context_rejects_cross_store_access(self):
        self._seed_full_store_data()
        token = self._mint_token(store_id=str(self.other_store.id))

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["store"]["id"], str(self.other_store.id))
        product_skus = {item["sku"] for item in response.data["products"]["items"]}
        self.assertIn("SKU-OTHER", product_skus)
        self.assertNotIn("SKU-A", product_skus)
        self.assertEqual(response.data["sales_summary"]["today"]["order_count"], 0)
        self.assertEqual(response.data["inventory"]["low_stock_count"], 0)
        self.assertEqual(response.data["messages"]["thread_count"], 0)

    def test_context_returns_expected_top_level_keys(self):
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), TOP_LEVEL_KEYS)

    def test_context_includes_safe_product_summary_data(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["products"]["count"], 1)
        product = response.data["products"]["items"][0]
        self.assertEqual(product["product_id"], str(self.product.id))
        self.assertEqual(product["name"], "Leather Tote")
        self.assertEqual(product["sku"], "SKU-A")
        self.assertEqual(product["currency"], "USD")
        self.assertTrue(product["is_active"])

    def test_context_includes_sales_summary_data(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sales = response.data["sales_summary"]
        self.assertEqual(sales["currency"], "USD")
        self.assertGreaterEqual(sales["today"]["order_count"], 1)
        self.assertIn("last_7_days", sales)

    def test_context_includes_low_stock_inventory_data(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["inventory"]["low_stock_count"], 1)
        self.assertEqual(response.data["inventory"]["items"][0]["sku"], "SKU-A")

    def test_context_includes_recent_sanitized_message_threads(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["messages"]["thread_count"], 1)
        thread = response.data["messages"]["threads"][0]
        self.assertTrue(thread["customer_ref"].startswith("customer-"))
        self.assertEqual(len(thread["messages"]), 1)

    def test_context_response_does_not_contain_raw_email_values(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        payload = json.dumps(response.data, default=str)
        self.assertNotIn("sara.jamali@example.com", payload)

    def test_context_response_does_not_contain_raw_phone_values(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        payload = json.dumps(response.data, default=str)
        for raw_value in RAW_PII_VALUES:
            self.assertNotIn(raw_value, payload)

    def test_context_response_does_not_contain_raw_pii_fields(self):
        self._seed_full_store_data()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        response_keys = self._collect_keys(response.data)
        for field_name in PII_FIELD_NAMES:
            self.assertNotIn(field_name, response_keys)

    def test_context_echoes_report_run_id_when_jwt_has_no_claim(self):
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["report_run_id"], str(self.report_run_id))

    def test_context_validates_matching_report_run_id_claim(self):
        token = self._mint_token(report_run_id=str(self.report_run_id))

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["report_run_id"], str(self.report_run_id))

    def test_context_rejects_mismatched_report_run_id_claim(self):
        token = self._mint_token(report_run_id=str(uuid.uuid4()))

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_context_returns_empty_sections_for_missing_optional_data(self):
        Product.objects.filter(store=self.store).delete()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["products"]["count"], 0)
        self.assertEqual(response.data["inventory"]["low_stock_count"], 0)
        self.assertEqual(response.data["messages"]["thread_count"], 0)
        self.assertEqual(response.data["sales_summary"]["today"]["order_count"], 0)
        self.assertEqual(response.data["warnings"], [])

    def test_context_missing_section_returns_warning_instead_of_500(self):
        token = self._mint_token()

        with patch(
            "catalog.context.build_sales_summary",
            side_effect=RuntimeError("simulated sales failure"),
        ):
            response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sales_summary"]["today"], {})
        self.assertIn("sales_summary unavailable", response.data["warnings"])

    def test_context_does_not_write_to_database(self):
        self._seed_full_store_data()
        before = self._model_counts()
        token = self._mint_token()

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._model_counts(), before)

    def test_context_returns_not_found_for_missing_store(self):
        missing_store_id = "00000000-0000-0000-0000-000000000099"
        token = self._mint_token(store_id=missing_store_id)

        response = self.client.get(self.context_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _collect_keys(self, obj):
        keys = set()
        if isinstance(obj, dict):
            keys.update(obj.keys())
            for value in obj.values():
                keys |= self._collect_keys(value)
        elif isinstance(obj, list):
            for item in obj:
                keys |= self._collect_keys(item)
        return keys
