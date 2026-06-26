from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SessionAuthentication
from operations.dashboard_serializers import HistoryFeedQuerySerializer
from operations.history_service import HistoryFeedService


class HistoryFeedView(APIView):
    """Dashboard-facing unified history feed (read-only)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        query_data = request.query_params.dict()
        if "from" in query_data:
            query_data["from_timestamp"] = query_data.pop("from")
        if "to" in query_data:
            query_data["to_timestamp"] = query_data.pop("to")

        serializer = HistoryFeedQuerySerializer(data=query_data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        pagination = {
            "limit": validated.pop("limit"),
            "offset": validated.pop("offset"),
        }

        result = HistoryFeedService.list_for_user(
            user=request.user,
            filters=validated,
            pagination=pagination,
            request=request,
        )
        return Response(result)
