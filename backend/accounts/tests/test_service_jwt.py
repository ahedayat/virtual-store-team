from datetime import datetime, timedelta, timezone

import jwt
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.constants import AI_SERVICE_COORDINATOR, AI_SERVICE_SALES
from accounts.models import User, UserRole
from accounts.service_jwt import (
    ExpiredServiceJWTError,
    InvalidServiceJWTAudienceError,
    InvalidServiceJWTError,
    ServiceJWTMintError,
    UnknownServiceError,
    decode_service_jwt,
    mint_service_jwt,
)
from stores.models import Store
from tenants.models import Tenant

TEST_JWT_SETTINGS = {
    "JWT_SERVICE_SECRET": "test-service-secret",
    "JWT_SERVICE_AUDIENCE": "ai-services",
    "JWT_SERVICE_ALGORITHM": "HS256",
    "JWT_SERVICE_TOKEN_LIFETIME_MINUTES": 30,
}

TENANT_ID = "tenant-uuid-1"
STORE_ID = "store-uuid-1"


@override_settings(**TEST_JWT_SETTINGS)
class ServiceJWTMintTests(SimpleTestCase):
    def _mint(self, **kwargs):
        defaults = {
            "service_name": AI_SERVICE_COORDINATOR,
            "tenant_id": TENANT_ID,
            "store_id": STORE_ID,
        }
        defaults.update(kwargs)
        return mint_service_jwt(**defaults)

    def test_mint_returns_string_token(self):
        token = self._mint()

        self.assertIsInstance(token, str)
        self.assertTrue(token)

    def test_minted_token_contains_required_claims_after_verification(self):
        token = self._mint()

        claims = decode_service_jwt(token)

        for claim in ("sub", "tenant_id", "store_id", "iat", "exp", "aud"):
            self.assertIn(claim, claims)

    def test_minted_token_contains_correct_sub(self):
        token = self._mint(service_name=AI_SERVICE_SALES)

        claims = decode_service_jwt(token)

        self.assertEqual(claims["sub"], AI_SERVICE_SALES)

    def test_minted_token_contains_correct_tenant_id(self):
        token = self._mint(tenant_id="custom-tenant-99")

        claims = decode_service_jwt(token)

        self.assertEqual(claims["tenant_id"], "custom-tenant-99")

    def test_minted_token_contains_correct_store_id(self):
        token = self._mint(store_id="custom-store-42")

        claims = decode_service_jwt(token)

        self.assertEqual(claims["store_id"], "custom-store-42")

    def test_minted_token_contains_correct_aud(self):
        token = self._mint()

        claims = decode_service_jwt(token)

        self.assertEqual(claims["aud"], TEST_JWT_SETTINGS["JWT_SERVICE_AUDIENCE"])

    def test_minted_token_includes_iat_and_exp(self):
        before = datetime.now(timezone.utc)
        token = self._mint()
        after = datetime.now(timezone.utc)

        claims = decode_service_jwt(token)

        iat = datetime.fromtimestamp(claims["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)

        self.assertGreaterEqual(iat, before - timedelta(seconds=2))
        self.assertLessEqual(iat, after + timedelta(seconds=2))
        self.assertIsInstance(exp, datetime)

    def test_exp_is_after_iat(self):
        token = self._mint()

        claims = decode_service_jwt(token)

        self.assertGreater(claims["exp"], claims["iat"])

    @override_settings(JWT_SERVICE_TOKEN_LIFETIME_MINUTES=45)
    def test_default_lifetime_uses_configured_minutes(self):
        token = self._mint()

        claims = decode_service_jwt(token)
        lifetime_seconds = claims["exp"] - claims["iat"]

        self.assertAlmostEqual(lifetime_seconds, 45 * 60, delta=2)

    def test_custom_lifetime_override(self):
        token = self._mint(lifetime_minutes=5)

        claims = decode_service_jwt(token)
        lifetime_seconds = claims["exp"] - claims["iat"]

        self.assertAlmostEqual(lifetime_seconds, 5 * 60, delta=2)

    def test_report_run_id_included_when_provided(self):
        token = self._mint(report_run_id="run-abc-123")

        claims = decode_service_jwt(token)

        self.assertEqual(claims["report_run_id"], "run-abc-123")

    def test_report_run_id_absent_when_not_provided(self):
        token = self._mint()

        claims = decode_service_jwt(token)

        self.assertNotIn("report_run_id", claims)

    def test_unknown_service_name_rejected_during_minting(self):
        with self.assertRaises(UnknownServiceError):
            self._mint(service_name="unknown-agent")

    def test_missing_tenant_id_rejected(self):
        with self.assertRaises(ServiceJWTMintError):
            self._mint(tenant_id="")

        with self.assertRaises(ServiceJWTMintError):
            self._mint(tenant_id=None)

    def test_missing_store_id_rejected(self):
        with self.assertRaises(ServiceJWTMintError):
            self._mint(store_id="")

        with self.assertRaises(ServiceJWTMintError):
            self._mint(store_id=None)


@override_settings(**TEST_JWT_SETTINGS)
class ServiceJWTVerifyTests(SimpleTestCase):
    def _base_payload(self, **overrides):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": AI_SERVICE_COORDINATOR,
            "tenant_id": TENANT_ID,
            "store_id": STORE_ID,
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "aud": TEST_JWT_SETTINGS["JWT_SERVICE_AUDIENCE"],
        }
        payload.update(overrides)
        return payload

    def _encode(self, payload, *, secret=None, algorithm=None):
        return jwt.encode(
            payload,
            secret or TEST_JWT_SETTINGS["JWT_SERVICE_SECRET"],
            algorithm=algorithm or TEST_JWT_SETTINGS["JWT_SERVICE_ALGORITHM"],
        )

    def test_valid_minted_token_verifies_successfully(self):
        token = mint_service_jwt(
            service_name=AI_SERVICE_COORDINATOR,
            tenant_id=TENANT_ID,
            store_id=STORE_ID,
        )

        claims = decode_service_jwt(token)

        self.assertEqual(claims["sub"], AI_SERVICE_COORDINATOR)
        self.assertEqual(claims["tenant_id"], TENANT_ID)
        self.assertEqual(claims["store_id"], STORE_ID)

    def test_token_signed_with_wrong_secret_is_rejected(self):
        token = self._encode(self._base_payload(), secret="wrong-signing-secret")

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)

    def test_token_with_wrong_audience_is_rejected(self):
        token = self._encode(self._base_payload(aud="wrong-audience"))

        with self.assertRaises(InvalidServiceJWTAudienceError):
            decode_service_jwt(token)

    def test_expired_token_is_rejected(self):
        now = datetime.now(timezone.utc)
        token = self._encode(
            self._base_payload(
                iat=now - timedelta(hours=2),
                exp=now - timedelta(hours=1),
            )
        )

        with self.assertRaises(ExpiredServiceJWTError):
            decode_service_jwt(token)

    def test_token_missing_sub_is_rejected(self):
        payload = self._base_payload()
        del payload["sub"]
        token = self._encode(payload)

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)

    def test_token_missing_tenant_id_is_rejected(self):
        payload = self._base_payload()
        del payload["tenant_id"]
        token = self._encode(payload)

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)

    def test_token_missing_store_id_is_rejected(self):
        payload = self._base_payload()
        del payload["store_id"]
        token = self._encode(payload)

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)

    def test_token_missing_aud_is_rejected(self):
        payload = self._base_payload()
        del payload["aud"]
        token = self._encode(payload)

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)

    def test_token_with_unknown_sub_is_rejected(self):
        token = self._encode(self._base_payload(sub="unknown-agent"))

        with self.assertRaises(UnknownServiceError):
            decode_service_jwt(token)

    def test_malformed_token_is_rejected(self):
        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt("not-a-valid-jwt")

    def test_empty_token_is_rejected(self):
        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt("")

    def test_unexpected_algorithm_is_rejected(self):
        token = self._encode(self._base_payload(), algorithm="HS384")

        with self.assertRaises(InvalidServiceJWTError):
            decode_service_jwt(token)


@override_settings(**TEST_JWT_SETTINGS)
class ServiceJWTIntegrationTests(APITestCase):
    """Phase 2.4 — minted tokens authenticate against the internal auth-check route."""

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

    def test_minted_token_can_access_internal_auth_check(self):
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

    def test_auth_check_response_includes_service_context(self):
        token = mint_service_jwt(
            service_name=AI_SERVICE_COORDINATOR,
            tenant_id=self.tenant_id,
            store_id=self.store_id,
        )

        response = self.client.get(self.auth_check_url, **self._auth_header(token))

        self.assertEqual(response.data["service_name"], AI_SERVICE_COORDINATOR)
        self.assertEqual(response.data["tenant_id"], self.tenant_id)
        self.assertEqual(response.data["store_id"], self.store_id)
        self.assertNotIn(token, str(response.data))

    def test_session_authenticated_user_cannot_access_without_service_jwt(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.auth_check_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
