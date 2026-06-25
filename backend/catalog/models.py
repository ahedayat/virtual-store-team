import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from stores.models import Store
from tenants.models import Tenant, TenantScopedModel


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    COMPLETED = "completed", "Completed"
    FULFILLED = "fulfilled", "Fulfilled"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"
    FAILED = "failed", "Failed"


REVENUE_COUNTABLE_ORDER_STATUSES = frozenset(
    {
        OrderStatus.PAID,
        OrderStatus.COMPLETED,
        OrderStatus.FULFILLED,
    }
)


class Category(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="categories",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="categories",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=63)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "slug"],
                name="catalog_category_unique_tenant_store_slug",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class Product(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="products",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=63)
    sku = models.CharField(max_length=63)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "slug"],
                name="catalog_product_unique_tenant_store_slug",
            ),
            models.UniqueConstraint(
                fields=["tenant", "store", "sku"],
                name="catalog_product_unique_tenant_store_sku",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if (
            self.category_id
            and self.store_id
            and self.category.store_id != self.store_id
        ):
            raise ValidationError(
                {"category": "Category must belong to the same store."}
            )

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Order(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    order_number = models.CharField(max_length=63)
    external_id = models.CharField(max_length=127, blank=True)
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    currency = models.CharField(max_length=3)
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    placed_at = models.DateTimeField(default=timezone.now)
    external_customer_ref = models.CharField(max_length=127, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-placed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "order_number"],
                name="catalog_order_unique_tenant_store_order_number",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "placed_at"],
                name="cat_order_tnt_store_placed",
            ),
            models.Index(
                fields=["tenant", "store", "status"],
                name="cat_order_tnt_store_status",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})

    @property
    def is_revenue_countable(self):
        return self.status in REVENUE_COUNTABLE_ORDER_STATUSES

    def __str__(self):
        return f"{self.order_number} ({self.store.name})"


class OrderItem(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    product_name_snapshot = models.CharField(max_length=255)
    sku_snapshot = models.CharField(max_length=63)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["order", "sku_snapshot"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "sku_snapshot"],
                name="catalog_orderitem_unique_order_sku",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "order"],
                name="cat_orditem_tnt_store_ord",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if self.order_id and self.store_id and self.order.store_id != self.store_id:
            raise ValidationError({"order": "Order must belong to the same store."})
        if self.product_id and self.store_id and self.product.store_id != self.store_id:
            raise ValidationError({"product": "Product must belong to the same store."})

    def __str__(self):
        return f"{self.sku_snapshot} x{self.quantity} ({self.order.order_number})"
