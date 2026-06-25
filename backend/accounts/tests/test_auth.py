from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from stores.models import Store
from tenants.models import Tenant


class AuthEndpointTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="acme", name="Acme Corp")
        self.other_tenant = Tenant.objects.create(slug="other", name="Other Corp")

        self.store = Store.objects.create(
            tenant=self.tenant,
            name="Main Store",
            slug="main",
            currency="USD",
        )
        self.other_store = Store.objects.create(
            tenant=self.other_tenant,
            name="Other Store",
            slug="main",
            currency="EUR",
        )

        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="secure-pass-123",
            full_name="Manager Name",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
        )
        self.inactive_manager = User.objects.create_user(
            email="inactive@example.com",
            password="secure-pass-123",
            full_name="Inactive Manager",
            role=UserRole.MANAGER,
            tenant=self.tenant,
            store=self.store,
            is_active=False,
        )

        self.login_url = reverse("auth-login")
        self.logout_url = reverse("auth-logout")
        self.me_url = reverse("auth-me")

    def test_manager_can_login_with_valid_credentials(self):
        response = self.client.post(
            self.login_url,
            {"email": "manager@example.com", "password": "secure-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "manager@example.com")
        self.assertEqual(response.data["user"]["full_name"], "Manager Name")
        self.assertEqual(response.data["user"]["role"], "manager")
        self.assertEqual(str(response.data["user"]["tenant"]["id"]), str(self.tenant.id))
        self.assertEqual(response.data["user"]["tenant"]["slug"], "acme")
        self.assertEqual(response.data["user"]["tenant"]["name"], "Acme Corp")
        self.assertEqual(str(response.data["user"]["store"]["id"]), str(self.store.id))
        self.assertEqual(response.data["user"]["store"]["slug"], "main")
        self.assertEqual(response.data["user"]["store"]["name"], "Main Store")

    def test_login_fails_with_invalid_password(self):
        response = self.client.post(
            self.login_url,
            {"email": "manager@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_cannot_login(self):
        response = self.client.post(
            self.login_url,
            {"email": "inactive@example.com", "password": "secure-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_call_me(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "manager@example.com")
        self.assertEqual(response.data["user"]["tenant"]["slug"], "acme")
        self.assertEqual(response.data["user"]["store"]["slug"], "main")

    def test_anonymous_user_cannot_call_me(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_logout(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Logged out successfully.")

    def test_after_logout_session_user_cannot_access_me(self):
        self.client.login(email="manager@example.com", password="secure-pass-123")

        logout_response = self.client.post(self.logout_url)
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        me_response = self.client.get(self.me_url)
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_does_not_expose_password_or_sensitive_tenant_settings(self):
        self.tenant.settings = {"api_secret": "super-secret"}
        self.tenant.save(update_fields=["settings"])

        response = self.client.post(
            self.login_url,
            {"email": "manager@example.com", "password": "secure-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant_payload = response.data["user"]["tenant"]
        self.assertNotIn("settings", tenant_payload)
        self.assertNotIn("password", response.data["user"])
