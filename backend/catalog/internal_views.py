from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import InternalAIAuthentication
from catalog.services import build_low_stock_summary, build_sales_summary
from stores.models import Store
from tenants.models import Tenant


class InternalSalesSummaryView(APIView):
    """Internal AI sales summary for a store (today and last 7 days)."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id):
        identity = request.ai_service
        store_id_str = str(store_id)

        if store_id_str != identity.store_id:
            raise PermissionDenied("Service token store does not match the requested store.")

        try:
            tenant = Tenant.objects.get(pk=identity.tenant_id)
        except Tenant.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        try:
            store = Store.objects.get_for_tenant(tenant, pk=store_id)
        except Store.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        return Response(build_sales_summary(store))


class InternalLowStockInventoryView(APIView):
    """Internal AI low-stock inventory report for a store."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id):
        identity = request.ai_service
        store_id_str = str(store_id)

        if store_id_str != identity.store_id:
            raise PermissionDenied("Service token store does not match the requested store.")

        try:
            tenant = Tenant.objects.get(pk=identity.tenant_id)
        except Tenant.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        try:
            store = Store.objects.get_for_tenant(tenant, pk=store_id)
        except Store.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        return Response(build_low_stock_summary(store))
