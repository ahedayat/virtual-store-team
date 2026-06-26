from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SessionAuthentication
from accounts.models import UserRole
from operations.dashboard_serializers import (
    ActionApproveRequestSerializer,
    ActionListQuerySerializer,
    ActionRejectRequestSerializer,
    DashboardPaginationQuerySerializer,
    HistoryFeedQuerySerializer,
)
from operations.dashboard_service import (
    DashboardActionService,
    DashboardReportService,
    DashboardScopeService,
)
from operations.exceptions import ActionTransitionError
from operations.history_service import HistoryFeedService
from operations.services import ActionService, ReportRunService
from operations.tasks import generate_daily


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


class ReportGenerateView(APIView):
    """Enqueue a queued ReportRun and trigger the daily report Celery task."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        user = request.user
        if user.role != UserRole.MANAGER and not user.is_staff:
            raise PermissionDenied("Only managers can trigger daily report generation.")

        store = user.store
        if store is None:
            raise ValidationError(
                {"detail": "Authenticated user must be scoped to a store to generate reports."}
            )
        if store.tenant_id != user.tenant_id:
            raise ValidationError({"detail": "User store does not belong to the user's tenant."})

        result = ReportRunService.create_queued_run_for_store(
            tenant=user.tenant,
            store=store,
        )
        if not result.created:
            existing = result.report_run
            return Response(
                {
                    "detail": "An active report run already exists for this store.",
                    "existing_report_run_id": str(existing.id),
                    "status": existing.status,
                    "created_at": existing.created_at,
                },
                status=status.HTTP_409_CONFLICT,
            )

        report_run = result.report_run
        async_result = generate_daily.delay(str(report_run.id))

        return Response(
            {
                "report_run_id": str(report_run.id),
                "status": report_run.status,
                "task_id": async_result.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ReportListView(APIView):
    """Dashboard-facing report run list (read-only)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        serializer = DashboardPaginationQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        result = DashboardReportService.list_for_user(
            user=request.user,
            pagination={
                "limit": validated["limit"],
                "offset": validated["offset"],
            },
            request=request,
        )
        return Response(result)


class ReportDetailView(APIView):
    """Dashboard-facing report run detail (read-only)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, report_run_id: UUID):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        report_run = DashboardScopeService.get_report_run(request.user, report_run_id)
        if report_run is None:
            raise NotFound("Report run not found.")

        return Response(DashboardReportService.serialize_report_run_detail(report_run))


class ActionListView(APIView):
    """Dashboard-facing action list (read-only)."""

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
        if "agent" in query_data:
            query_data["agent_name"] = query_data.pop("agent")

        serializer = ActionListQuerySerializer(data=query_data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        pagination = {
            "limit": validated.pop("limit"),
            "offset": validated.pop("offset"),
        }

        result = DashboardActionService.list_for_user(
            user=request.user,
            filters=validated,
            pagination=pagination,
            request=request,
        )
        return Response(result)


class ActionDetailView(APIView):
    """Dashboard-facing action detail (read-only)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, action_id: UUID):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        action = DashboardScopeService.get_action(request.user, action_id)
        if action is None:
            raise NotFound("Action not found.")

        return Response(DashboardActionService.serialize_action(action))


class ActionApproveView(APIView):
    """Manager approval for a pending action."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: UUID):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        user = request.user
        if user.role != UserRole.MANAGER and not user.is_staff:
            raise PermissionDenied("Only managers can approve actions.")

        action = DashboardScopeService.get_action(user, action_id)
        if action is None:
            raise NotFound("Action not found.")

        if not DashboardScopeService.user_can_decide_on_action(user, action):
            raise NotFound("Action not found.")

        serializer = ActionApproveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason") or None

        try:
            updated = ActionService.approve(action=action, actor=user, reason=reason)
        except ActionTransitionError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(DashboardActionService.serialize_action(updated))


class ActionRejectView(APIView):
    """Manager rejection for a pending action."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: UUID):
        if not request.user.is_authenticated:
            raise NotAuthenticated()

        user = request.user
        if user.role != UserRole.MANAGER and not user.is_staff:
            raise PermissionDenied("Only managers can reject actions.")

        action = DashboardScopeService.get_action(user, action_id)
        if action is None:
            raise NotFound("Action not found.")

        if not DashboardScopeService.user_can_decide_on_action(user, action):
            raise NotFound("Action not found.")

        serializer = ActionRejectRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        try:
            updated = ActionService.reject(action=action, actor=user, reason=reason)
        except ActionTransitionError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(DashboardActionService.serialize_action(updated))
