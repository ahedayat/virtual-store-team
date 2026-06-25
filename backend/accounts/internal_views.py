from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import InternalAIAuthentication


class InternalAIAuthCheckView(APIView):
    """Minimal endpoint to verify InternalAIAuthentication for Phase 2.2."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        identity = request.ai_service
        return Response(
            {
                "detail": "Internal AI authentication successful.",
                "service_name": identity.service_name,
                "tenant_id": identity.tenant_id,
                "store_id": identity.store_id,
            }
        )
