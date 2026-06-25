import uuid

from django.db import models

from tenants.managers import TenantScopedManager


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=63, unique=True)
    name = models.CharField(max_length=255)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantScopedModel(models.Model):
    """Abstract base for models owned by a tenant.

    Subclasses must define a ``tenant`` foreign key. Use ``objects.for_tenant()``
    or ``objects.get_for_tenant()`` for tenant-scoped access paths.
    """

    objects = TenantScopedManager()

    class Meta:
        abstract = True
