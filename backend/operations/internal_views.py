import logging

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import InternalAIAuthentication
from operations.exceptions import ActionPayloadValidationError, ActionScopeError
from operations.internal_serializers import (
    InternalActionCreateRequestSerializer,
    InternalActionCreateResponseSerializer,
    InternalAgentOutputCreateRequestSerializer,
    InternalAgentOutputCreateResponseSerializer,
)
from operations.internal_utils import (
    resolve_agent_output,
    resolve_report_run,
    resolve_tenant_and_store,
)
from operations.services import ActionService, AgentOutputService

logger = logging.getLogger(__name__)


class InternalActionCreateView(APIView):
    """Persist a suggested action from an authenticated AI service."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InternalActionCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant, store = resolve_tenant_and_store(request)
        validated = serializer.validated_data
        report_run = resolve_report_run(
            tenant=tenant,
            store=store,
            report_run_id=validated.get("report_run_id"),
        )
        source_agent_output = resolve_agent_output(
            tenant=tenant,
            store=store,
            agent_output_id=validated.get("agent_output_id"),
        )

        try:
            action = ActionService.create_from_agent_payload(
                tenant=tenant,
                store=store,
                agent_name=request.service_name,
                payload=serializer.build_service_payload(),
                report_run=report_run,
                source_agent_output=source_agent_output,
            )
        except ActionPayloadValidationError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        except ActionScopeError as exc:
            raise NotFound(str(exc)) from exc

        logger.info(
            "Created action id=%s tenant_id=%s store_id=%s service_name=%s report_run_id=%s",
            action.id,
            tenant.id,
            store.id,
            request.service_name,
            report_run.id if report_run else None,
        )

        return Response(
            InternalActionCreateResponseSerializer(action).data,
            status=status.HTTP_201_CREATED,
        )


class InternalAgentOutputCreateView(APIView):
    """Persist structured output from an authenticated AI service."""

    authentication_classes = [InternalAIAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InternalAgentOutputCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant, store = resolve_tenant_and_store(request)
        validated = serializer.validated_data
        report_run = resolve_report_run(
            tenant=tenant,
            store=store,
            report_run_id=validated.get("report_run_id"),
        )

        agent_output = AgentOutputService.create_from_agent_payload(
            tenant=tenant,
            store=store,
            agent_name=request.service_name,
            output_type=validated["output_type"],
            payload=validated["payload"],
            metadata=validated.get("metadata"),
            report_run=report_run,
        )

        logger.info(
            "Created agent output id=%s tenant_id=%s store_id=%s service_name=%s report_run_id=%s",
            agent_output.id,
            tenant.id,
            store.id,
            request.service_name,
            report_run.id if report_run else None,
        )

        return Response(
            InternalAgentOutputCreateResponseSerializer(agent_output).data,
            status=status.HTTP_201_CREATED,
        )
