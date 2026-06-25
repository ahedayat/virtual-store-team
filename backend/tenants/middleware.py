import uuid

from django.contrib.auth.models import AnonymousUser

from tenants.models import Tenant

# Session key for MVP tenant resolution. Subdomain-based resolution is a future extension.
ACTIVE_TENANT_ID_SESSION_KEY = "active_tenant_id"


def get_tenant_by_id(tenant_id):
    """Return a Tenant for the given ID, or None if the ID is missing or invalid."""
    if tenant_id is None:
        return None

    try:
        tenant_uuid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
    except (ValueError, TypeError, AttributeError):
        return None

    try:
        return Tenant.objects.get(pk=tenant_uuid)
    except Tenant.DoesNotExist:
        return None


def resolve_tenant_from_user(user):
    """Resolve tenant from an authenticated user with tenant or tenant_id attributes."""
    if user is None or isinstance(user, AnonymousUser):
        return None

    is_authenticated = getattr(user, "is_authenticated", False)
    if not is_authenticated:
        return None

    tenant = getattr(user, "tenant", None)
    if tenant is not None:
        return tenant

    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id is not None:
        return get_tenant_by_id(tenant_id)

    return None


def resolve_tenant_from_session(session):
    """Resolve tenant from the active tenant ID stored in the session."""
    if session is None:
        return None

    tenant_id = session.get(ACTIVE_TENANT_ID_SESSION_KEY)
    if tenant_id is None:
        return None

    return get_tenant_by_id(tenant_id)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        request.tenant_id = None

        tenant = resolve_tenant_from_user(getattr(request, "user", None))
        if tenant is None:
            tenant = resolve_tenant_from_session(getattr(request, "session", None))

        if tenant is not None:
            request.tenant = tenant
            request.tenant_id = tenant.id

        return self.get_response(request)
