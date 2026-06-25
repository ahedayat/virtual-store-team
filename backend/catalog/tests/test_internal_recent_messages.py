import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_SUPPORT
from accounts.service_jwt import mint_service_jwt
from catalog.models import (
    Customer,
    Message,
    MessageDirection,
    MessageThread,
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


@override_settings(**TEST_JWT_SETTINGS)
class InternalRecentMessagesAPITests(APITestCase):
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
        self.recent_messages_url = reverse(
            "internal-ai-recent-messages",
            kwargs={"store_id": self.store.id},
        )

    def _mint_token(self, **kwargs):
        return mint_service_jwt(
            service_name=kwargs.get("service_name", AI_SERVICE_SUPPORT),
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _seed_support_messages(self):
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

    def test_recent_messages_requires_service_jwt(self):
        response = self.client.get(self.recent_messages_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recent_messages_accepts_valid_service_jwt(self):
        self._seed_support_messages()
        token = self._mint_token()

        response = self.client.get(self.recent_messages_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["store_id"], self.store_id)
        self.assertEqual(response.data["thread_count"], 1)
        self.assertEqual(len(response.data["threads"][0]["messages"]), 1)

    def test_recent_messages_rejects_cross_store_access(self):
        token = self._mint_token(store_id=str(self.other_store.id))

        response = self.client.get(self.recent_messages_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recent_messages_rejects_cross_tenant_store_access(self):
        token = self._mint_token()
        url = reverse(
            "internal-ai-recent-messages",
            kwargs={"store_id": self.foreign_store.id},
        )

        response = self.client.get(url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recent_messages_returns_not_found_for_missing_store(self):
        missing_store_id = "00000000-0000-0000-0000-000000000099"
        token = self._mint_token(store_id=missing_store_id)
        url = reverse(
            "internal-ai-recent-messages",
            kwargs={"store_id": missing_store_id},
        )

        response = self.client.get(url, **self._auth_header(token))

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

    def test_recent_messages_response_does_not_contain_raw_pii(self):
        self._seed_support_messages()
        token = self._mint_token()

        response = self.client.get(self.recent_messages_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = json.dumps(response.data, default=str)
        response_keys = self._collect_keys(response.data)
        for field_name in PII_FIELD_NAMES:
            self.assertNotIn(field_name, response_keys)
        for raw_value in RAW_PII_VALUES:
            self.assertNotIn(raw_value, payload)
