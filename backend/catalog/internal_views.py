from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import InternalAIAuthentication
from catalog.services import build_sales_summary
from stores.models import Store
from tenants.models import Tenant


class InternalAISalesSummaryView(APIView):
    """Internal AI sales summary for a store (today and last 7 days)."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id):
        identity = request.ai_service

        if str(store_id) != identity.store_id:
            raise PermissionDenied("Store scope does not match service token.")

        try:
            tenant = Tenant.objects.get(id=identity.tenant_id)
        except Tenant.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        try:
            store = Store.objects.get_for_tenant(tenant, id=store_id)
        except Store.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        summary = build_sales_summary(store)
        return Response(summary)
