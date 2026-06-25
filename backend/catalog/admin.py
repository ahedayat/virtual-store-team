from django.contrib import admin

from catalog.models import Category, Order, OrderItem, Product


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
