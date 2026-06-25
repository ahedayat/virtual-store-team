from django.test import override_settings
from django.urls import reverse
import jwt
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR, AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import mint_service_jwt
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-jwt-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}


@override_settings(**TEST_JWT_SETTINGS)
class InternalAIAuthenticationTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="acme", name="Acme Corp")
        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Main Store",
            slug="main",
            currency="USD",
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="secure-pass-123",
            full_name="Manager Name",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        self.auth_check_url = reverse("internal-ai-auth-check")
        self.tenant_id = str(self.tenant.id)
        self.store_id = str(self.store.id)

    def _mint_token(self, service_name=AI_SERVICE_COORDINATOR, **kwargs):
        return mint_service_jwt(
            service_name=service_name,
            tenant_id=kwargs.get("tenant_id", self.tenant_id),
            store_id=kwargs.get("store_id", self.store_id),
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_valid_service_jwt_can_access_auth_check(self):
        token = self._mint_token()

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Internal AI authentication successful.",
        )
        self.assertEqual(response.data["service_name"], AI_SERVICE_COORDINATOR)
        self.assertEqual(response.data["tenant_id"], self.tenant_id)
        self.assertEqual(response.data["store_id"], self.store_id)

    def test_missing_authorization_header_is_rejected(self):
        response = self.client.get(self.auth_check_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_bearer_authorization_header_is_rejected(self):
        response = self.client.get(
            self.auth_check_url,
            HTTP_AUTHORIZATION="Token some-value",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_bearer_token_is_rejected(self):
        response = self.client.get(
            self.auth_check_url,
            HTTP_AUTHORIZATION="Bearer not-a-valid-jwt",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_service_name_is_rejected(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "unknown-agent",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "aud": TEST_JWT_SETTINGS["JWT_SERVICE_AUDIENCE"],
        }
        token = jwt.encode(
            payload,
            TEST_JWT_SETTINGS["JWT_SERVICE_SECRET"],
            algorithm=TEST_JWT_SETTINGS["JWT_SERVICE_ALGORITHM"],
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_authenticated_user_cannot_access_without_service_jwt(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.auth_check_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_allowed_service_name_is_accepted(self):
        token = self._mint_token(service_name=AI_SERVICE_SALES)

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["service_name"], AI_SERVICE_SALES)
