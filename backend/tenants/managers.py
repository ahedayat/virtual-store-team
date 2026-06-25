from django.db import models


class TenantScopedQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        """Return rows belonging to the given tenant, or none() when tenant is missing."""
        if tenant is None:
            return self.none()
        return self.filter(tenant=tenant)

    def for_request(self, request):
        """Return rows for request.tenant, or none() when no tenant is resolved."""
        return self.for_tenant(getattr(request, "tenant", None))


class TenantScopedManager(models.Manager.from_queryset(TenantScopedQuerySet)):
    def get_for_tenant(self, tenant, **lookup):
        """Fetch a single row scoped to tenant; denies access when tenant is missing."""
        if tenant is None:
            raise self.model.DoesNotExist
        return self.for_tenant(tenant).get(**lookup)
