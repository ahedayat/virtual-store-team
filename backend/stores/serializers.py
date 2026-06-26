from rest_framework import serializers

from stores.models import Store
from tenants.models import Tenant


class TenantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "slug", "name")


class StoreReadSerializer(serializers.ModelSerializer):
    tenant = TenantSummarySerializer(read_only=True)

    class Meta:
        model = Store
        fields = ("id", "tenant", "name", "slug", "timezone", "currency")
