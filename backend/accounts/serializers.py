from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import User
from stores.models import Store
from tenants.models import Tenant


class TenantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "slug", "name")


class StoreSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ("id", "slug", "name")


class AuthenticatedUserSerializer(serializers.ModelSerializer):
    tenant = TenantSummarySerializer(read_only=True)
    store = StoreSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "tenant", "store")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationFailed("This account is inactive.")

        attrs["user"] = user
        return attrs
