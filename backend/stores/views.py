from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SessionAuthentication
from stores.models import Store
from stores.serializers import StoreReadSerializer


class StoreDetailView(APIView):
    """Read-only store detail scoped to the authenticated user's tenant."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        tenant = request.user.tenant
        try:
            store = Store.objects.get_for_tenant(tenant, pk=store_id)
        except Store.DoesNotExist as exc:
            raise NotFound("Store not found.") from exc

        return Response(StoreReadSerializer(store).data)
