from datetime import datetime, timedelta, timezone

import jwt
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR
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
class InternalAIServiceJWT401Tests(APITestCase):
    """Phase 2.3 — focused tests for safe 401 rejection on internal AI routes."""

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

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _encode_payload(self, payload, secret=None, algorithm=None):
        return jwt.encode(
            payload,
            secret or TEST_JWT_SETTINGS["JWT_SERVICE_SECRET"],
            algorithm=algorithm or TEST_JWT_SETTINGS["JWT_SERVICE_ALGORITHM"],
        )

    def _base_payload(self, **overrides):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": AI_SERVICE_COORDINATOR,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "aud": TEST_JWT_SETTINGS["JWT_SERVICE_AUDIENCE"],
        }
        payload.update(overrides)
        return payload

    def _assert_401_with_safe_body(self, response, expected_detail=None):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
        body = str(response.data)
        self.assertNotIn(TEST_JWT_SETTINGS["JWT_SERVICE_SECRET"], body)
        self.assertNotIn("PyJWT", body)
        self.assertNotIn("Traceback", body)
        if expected_detail is not None:
            self.assertEqual(response.data["detail"], expected_detail)

    def test_expired_service_jwt_returns_401(self):
        now = datetime.now(timezone.utc)
        token = self._encode_payload(
            self._base_payload(
                iat=now - timedelta(hours=2),
                exp=now - timedelta(hours=1),
            )
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self._assert_401_with_safe_body(
            response,
            expected_detail="Internal service token has expired.",
        )

    def test_wrong_audience_service_jwt_returns_401(self):
        token = self._encode_payload(
            self._base_payload(aud="wrong-audience"),
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token audience.",
        )

    def test_invalid_signature_returns_401(self):
        token = self._encode_payload(
            self._base_payload(),
            secret="wrong-signing-secret",
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token.",
        )

    def test_missing_required_claim_returns_401(self):
        for claim in ("sub", "tenant_id", "store_id", "exp", "aud"):
            with self.subTest(missing_claim=claim):
                payload = self._base_payload()
                del payload[claim]
                token = self._encode_payload(payload)

                response = self.client.get(
                    self.auth_check_url,
                    **self._auth_header(token),
                )

                self._assert_401_with_safe_body(
                    response,
                    expected_detail="Invalid internal service token.",
                )

    def test_unknown_service_name_returns_401(self):
        token = self._encode_payload(
            self._base_payload(sub="unknown-agent"),
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token.",
        )

    def test_malformed_token_returns_401(self):
        response = self.client.get(
            self.auth_check_url,
            HTTP_AUTHORIZATION="Bearer not-a-valid-jwt",
        )

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token.",
        )

    def test_empty_bearer_token_returns_401(self):
        response = self.client.get(
            self.auth_check_url,
            HTTP_AUTHORIZATION="Bearer ",
        )

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token.",
        )

    def test_bearer_keyword_without_token_returns_401(self):
        response = self.client.get(
            self.auth_check_url,
            HTTP_AUTHORIZATION="Bearer",
        )

        self._assert_401_with_safe_body(
            response,
            expected_detail="Invalid internal service token.",
        )

    def test_session_authenticated_manager_cannot_access_without_service_jwt(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.auth_check_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_valid_service_jwt_still_succeeds_after_hardening(self):
        token = mint_service_jwt(
            service_name=AI_SERVICE_COORDINATOR,
            tenant_id=self.tenant_id,
            store_id=self.store_id,
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Internal AI authentication successful.",
        )
        self.assertEqual(response.data["service_name"], AI_SERVICE_COORDINATOR)
        self.assertNotIn(token, str(response.data))

    def test_response_does_not_echo_raw_token(self):
        token = self._encode_payload(
            self._base_payload(
                sub="unknown-agent",
            ),
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(token, str(response.content))
