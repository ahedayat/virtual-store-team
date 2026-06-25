from django.contrib import admin

from catalog.models import (
    Category,
    Customer,
    InventoryLevel,
    Message,
    MessageThread,
    Order,
    OrderItem,
    Product,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("id",)
    fields = (
        "product",
        "product_name_snapshot",
        "sku_snapshot",
        "quantity",
        "unit_price",
        "line_total",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tenant", "store", "is_active")
    list_filter = ("tenant", "store", "is_active")
    search_fields = ("name", "slug", "description", "tenant__name", "tenant__slug")
    ordering = ("tenant", "store", "name")
    readonly_fields = ("id",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "slug",
        "tenant",
        "store",
        "category",
        "price",
        "is_active",
    )
    list_filter = ("tenant", "store", "category", "is_active")
    search_fields = (
        "name",
        "slug",
        "sku",
        "description",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("tenant", "store", "name")
    readonly_fields = ("id",)


@admin.register(InventoryLevel)
class InventoryLevelAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "sku_display",
        "tenant",
        "store",
        "quantity_on_hand",
        "reserved_quantity",
        "available_quantity_display",
        "low_stock_threshold",
        "is_active",
        "updated_at",
    )
    list_filter = ("tenant", "store", "is_active", "product__category")
    search_fields = (
        "product__name",
        "product__sku",
        "location_name",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("tenant", "store", "product__name")
    readonly_fields = ("id", "available_quantity_display", "updated_at")

    @admin.display(description="SKU")
    def sku_display(self, obj):
        return obj.product.sku

    @admin.display(description="Available")
    def available_quantity_display(self, obj):
        return obj.available_quantity


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "status",
        "tenant",
        "store",
        "total_amount",
        "currency",
        "placed_at",
    )
    list_filter = ("tenant", "store", "status", "currency")
    search_fields = (
        "order_number",
        "external_id",
        "external_customer_ref",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("-placed_at",)
    readonly_fields = ("id",)
    inlines = [OrderItemInline]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")
    fields = (
        "direction",
        "sender_type",
        "body",
        "external_message_id",
        "sent_at",
    )
    ordering = ("sent_at",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "platform",
        "platform_user_id",
        "email",
        "phone",
        "tenant",
        "store",
        "created_at",
    )
    list_filter = ("tenant", "store", "platform")
    search_fields = (
        "display_name",
        "email",
        "phone",
        "platform_user_id",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("tenant", "store", "display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "customer",
        "platform",
        "status",
        "last_message_at",
        "tenant",
        "store",
    )
    list_filter = ("tenant", "store", "platform", "status")
    search_fields = (
        "subject",
        "external_thread_id",
        "customer__display_name",
        "customer__platform_user_id",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("-last_message_at",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "thread",
        "direction",
        "sender_type",
        "sent_at",
        "tenant",
        "store",
    )
    list_filter = ("tenant", "store", "direction", "sender_type")
    search_fields = (
        "body",
        "external_message_id",
        "thread__subject",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("-sent_at",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "sku_snapshot",
        "product_name_snapshot",
        "quantity",
        "unit_price",
        "line_total",
        "tenant",
        "store",
    )
    list_filter = ("tenant", "store")
    search_fields = (
        "sku_snapshot",
        "product_name_snapshot",
        "order__order_number",
        "tenant__name",
        "tenant__slug",
    )
    ordering = ("-order__placed_at", "sku_snapshot")
    readonly_fields = ("id",)
