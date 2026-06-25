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


class InventoryLevel(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="inventory_levels",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="inventory_levels",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_levels",
    )
    quantity_on_hand = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField()
    reorder_target = models.PositiveIntegerField(null=True, blank=True)
    location_name = models.CharField(max_length=127, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "product"],
                name="catalog_inventory_unique_tenant_store_product",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "is_active"],
                name="cat_inv_tnt_store_active",
            ),
            models.Index(
                fields=["tenant", "store", "product"],
                name="cat_inv_tnt_store_product",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if self.product_id and self.store_id and self.product.store_id != self.store_id:
            raise ValidationError({"product": "Product must belong to the same store."})
        if self.reserved_quantity > self.quantity_on_hand:
            raise ValidationError(
                {"reserved_quantity": "Reserved quantity cannot exceed quantity on hand."}
            )

    @property
    def available_quantity(self):
        return self.quantity_on_hand - self.reserved_quantity

    def __str__(self):
        return f"{self.product.sku} ({self.available_quantity} available)"


class Platform(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    WEB = "web", "Web"
    MANUAL = "manual", "Manual"


class ThreadStatus(models.TextChoices):
    OPEN = "open", "Open"
    PENDING = "pending", "Pending"
    CLOSED = "closed", "Closed"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class SenderType(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"
    SYSTEM = "system", "System"


class Customer(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="customers",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="customers",
    )
    display_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=31, blank=True)
    platform_user_id = models.CharField(max_length=127, blank=True)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.MANUAL)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "platform", "platform_user_id"],
                condition=models.Q(platform_user_id__gt=""),
                name="catalog_customer_unique_platform_user",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "platform"],
                name="cat_cust_tnt_store_platform",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})

    def __str__(self):
        label = self.display_name or self.platform_user_id or str(self.id)
        return f"{label} ({self.store.name})"


class MessageThread(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="message_threads",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="message_threads",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="threads",
    )
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.MANUAL)
    external_thread_id = models.CharField(max_length=127, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ThreadStatus.choices,
        default=ThreadStatus.OPEN,
    )
    last_message_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "store", "external_thread_id"],
                condition=models.Q(external_thread_id__gt=""),
                name="catalog_thread_unique_external_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "platform", "status"],
                name="cat_thread_tnt_store_plat_stat",
            ),
            models.Index(
                fields=["tenant", "store", "last_message_at"],
                name="cat_thread_tnt_store_last_msg",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if self.customer_id and self.store_id and self.customer.store_id != self.store_id:
            raise ValidationError({"customer": "Customer must belong to the same store."})
        if self.customer_id and self.tenant_id and self.customer.tenant_id != self.tenant_id:
            raise ValidationError({"customer": "Customer must belong to the same tenant."})

    def __str__(self):
        label = self.subject or self.external_thread_id or str(self.id)
        return f"{label} ({self.store.name})"


class Message(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    thread = models.ForeignKey(
        MessageThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=20, choices=MessageDirection.choices)
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    body = models.TextField()
    external_message_id = models.CharField(max_length=127, blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["thread", "sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "external_message_id"],
                condition=models.Q(external_message_id__gt=""),
                name="catalog_message_unique_external_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "store", "thread", "sent_at"],
                name="cat_msg_tnt_store_thread_sent",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if self.thread_id and self.store_id and self.thread.store_id != self.store_id:
            raise ValidationError({"thread": "Thread must belong to the same store."})
        if self.thread_id and self.tenant_id and self.thread.tenant_id != self.tenant_id:
            raise ValidationError({"thread": "Thread must belong to the same tenant."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.thread_id:
            thread = self.thread
            if thread.last_message_at < self.sent_at:
                thread.last_message_at = self.sent_at
                thread.save(update_fields=["last_message_at", "updated_at"])

    def __str__(self):
        preview = self.body[:50] + ("..." if len(self.body) > 50 else "")
        return f"{self.direction} ({preview})"
