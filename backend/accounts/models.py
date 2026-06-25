import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from stores.models import Store
from tenants.models import Tenant

from accounts.managers import UserManager


class UserRole(models.TextChoices):
    MANAGER = "manager", "Manager"
    VIEWER = "viewer", "Viewer"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.MANAGER,
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="users",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        if self.store_id is not None and self.tenant_id is not None:
            if self.store.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"store": "Store must belong to the user's tenant."}
                )
