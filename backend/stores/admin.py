from django.contrib import admin

from stores.models import Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tenant", "timezone", "currency")
    search_fields = ("name", "slug", "tenant__name", "tenant__slug")
    list_filter = ("tenant", "currency")
