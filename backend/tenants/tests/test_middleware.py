from unittest.mock import Mock

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from tenants.middleware import (
    ACTIVE_TENANT_ID_SESSION_KEY,
    TenantMiddleware,
    get_tenant_by_id,
    resolve_tenant_from_session,
    resolve_tenant_from_user,
)
from tenants.models import Tenant


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda request: HttpResponse("ok"))
        self.tenant = Tenant.objects.create(slug="acme", name="Acme Corp")

    def _process_request(self, request):
        return self.middleware(request)

    def test_sets_tenant_none_when_no_tenant_is_available(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()

        self._process_request(request)

        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_id)

    def test_resolves_tenant_from_session(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session[ACTIVE_TENANT_ID_SESSION_KEY] = str(self.tenant.id)
        request.session.save()

        self._process_request(request)

        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.tenant_id, self.tenant.id)

    def test_handles_invalid_session_tenant_id_safely(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session[ACTIVE_TENANT_ID_SESSION_KEY] = "not-a-valid-uuid"
        request.session.save()

        self._process_request(request)

        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_id)

    def test_handles_unknown_session_tenant_id_safely(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session[ACTIVE_TENANT_ID_SESSION_KEY] = "00000000-0000-0000-0000-000000000000"
        request.session.save()

        self._process_request(request)

        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_id)

    def test_resolves_tenant_from_authenticated_user_tenant_attribute(self):
        request = self.factory.get("/")
        request.user = Mock(is_authenticated=True, tenant=self.tenant, tenant_id=self.tenant.id)
        request.session = SessionStore()

        self._process_request(request)

        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.tenant_id, self.tenant.id)

    def test_resolves_tenant_from_authenticated_user_tenant_id_attribute(self):
        request = self.factory.get("/")
        request.user = Mock(is_authenticated=True, tenant_id=self.tenant.id)
        del request.user.tenant

        self._process_request(request)

        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.tenant_id, self.tenant.id)

    def test_user_tenant_takes_precedence_over_session(self):
        other_tenant = Tenant.objects.create(slug="other", name="Other Corp")
        request = self.factory.get("/")
        request.user = Mock(is_authenticated=True, tenant=self.tenant, tenant_id=self.tenant.id)
        request.session = SessionStore()
        request.session[ACTIVE_TENANT_ID_SESSION_KEY] = str(other_tenant.id)
        request.session.save()

        self._process_request(request)

        self.assertEqual(request.tenant, self.tenant)

    def test_does_not_crash_for_anonymous_requests_without_session(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = self._process_request(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_id)

    def test_middleware_is_registered_after_session_and_auth(self):
        middleware = settings.MIDDLEWARE
        session_index = middleware.index("django.contrib.sessions.middleware.SessionMiddleware")
        auth_index = middleware.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        tenant_index = middleware.index("tenants.middleware.TenantMiddleware")

        self.assertGreater(tenant_index, session_index)
        self.assertGreater(tenant_index, auth_index)


class TenantResolutionHelperTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug="helpers", name="Helpers Inc")

    def test_get_tenant_by_id_returns_none_for_invalid_uuid(self):
        self.assertIsNone(get_tenant_by_id("invalid"))

    def test_resolve_tenant_from_user_returns_none_for_anonymous_user(self):
        self.assertIsNone(resolve_tenant_from_user(AnonymousUser()))

    def test_resolve_tenant_from_session_returns_none_when_key_missing(self):
        session = SessionStore()
        self.assertIsNone(resolve_tenant_from_session(session))
