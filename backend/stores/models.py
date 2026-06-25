import uuid

from django.db import models

from tenants.models import Tenant, TenantScopedModel


class Store(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="stores",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=63)
    timezone = models.CharField(max_length=63, default="UTC")
    currency = models.CharField(max_length=3)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="stores_store_unique_tenant_slug",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
