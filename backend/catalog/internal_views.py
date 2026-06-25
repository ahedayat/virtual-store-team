from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import InternalAIAuthentication
from catalog.context import build_context_bundle
from catalog.services import (
    build_low_stock_summary,
    build_recent_messages_summary,
    build_sales_summary,
)
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


class InternalRecentMessagesView(APIView):
    """Internal AI recent support messages for a store (sanitized)."""

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

        thread_limit = self._parse_limit(request.query_params.get("thread_limit"), default=10)
        messages_per_thread = self._parse_limit(
            request.query_params.get("messages_per_thread"),
            default=5,
        )

        return Response(
            build_recent_messages_summary(
                store,
                thread_limit=thread_limit,
                messages_per_thread=messages_per_thread,
            )
        )

    @staticmethod
    def _parse_limit(value: str | None, *, default: int) -> int:
        if value is None:
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, min(parsed, 50))


class InternalAIContextView(APIView):
    """Internal AI context bundle for coordinator-agent consumption (read-only stub)."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, report_run_id):
        identity = request.ai_service
        report_run_id_str = str(report_run_id)
        claims = request.auth or {}

        jwt_report_run_id = claims.get("report_run_id")
        if jwt_report_run_id is not None and str(jwt_report_run_id) != report_run_id_str:
            raise PermissionDenied(
                "Service token report_run_id does not match the requested report run."
            )

        try:
            tenant = Tenant.objects.get(pk=identity.tenant_id)
        except Tenant.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        try:
            store = Store.objects.get_for_tenant(tenant, pk=identity.store_id)
        except Store.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        return Response(
            build_context_bundle(
                tenant=tenant,
                store=store,
                report_run_id=report_run_id_str,
            )
        )
