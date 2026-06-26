from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from django.utils import timezone

from accounts.models import User
from operations.history_constants import DEFAULT_HISTORY_LIMIT, MAX_HISTORY_LIMIT
from operations.models import Action, DailyReport, ReportRun
from stores.models import Store
from tenants.models import Tenant

SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "email",
        "phone",
        "address",
        "customer_name",
        "customer_email",
        "customer_phone",
        "draft_text",
        "reply_text",
        "message_body",
        "body",
    }
)

SAFE_PAYLOAD_KEYS = frozenset(
    {
        "sku",
        "product_id",
        "current_stock",
        "suggested_order_qty",
        "thread_id",
        "order_ref",
        "rationale",
        "discount_percent",
        "campaign_angle",
        "content_type",
        "low_risk",
    }
)


class DashboardScopeService:
    @staticmethod
    def resolve_scope(user: User) -> tuple[Tenant, Store | None]:
        return user.tenant, user.store

    @classmethod
    def scoped_report_runs(cls, user: User):
        tenant, store = cls.resolve_scope(user)
        queryset = ReportRun.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("store", "daily_report")

    @classmethod
    def get_report_run(cls, user: User, report_run_id: UUID) -> ReportRun | None:
        return cls.scoped_report_runs(user).filter(pk=report_run_id).first()

    @classmethod
    def scoped_actions(cls, user: User):
        tenant, store = cls.resolve_scope(user)
        queryset = Action.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("store", "report_run", "decided_by")

    @classmethod
    def get_action(cls, user: User, action_id: UUID) -> Action | None:
        return cls.scoped_actions(user).filter(pk=action_id).first()

    @classmethod
    def user_can_decide_on_action(cls, user: User, action: Action) -> bool:
        tenant, store = cls.resolve_scope(user)
        if action.tenant_id != tenant.id:
            return False
        if store is not None and action.store_id != store.id:
            return False
        return True


class DashboardReportService:
    @classmethod
    def list_for_user(
        cls,
        *,
        user: User,
        pagination: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        pagination = pagination or {}
        queryset = DashboardScopeService.scoped_report_runs(user).order_by("-created_at")
        return cls._paginate_queryset(
            queryset,
            serializer=cls.serialize_report_run_summary,
            pagination=pagination,
            request=request,
            filters={},
        )

    @classmethod
    def serialize_report_run_summary(cls, report_run: ReportRun) -> dict[str, Any]:
        daily_report = getattr(report_run, "daily_report", None)
        if daily_report is None:
            try:
                daily_report = report_run.daily_report
            except DailyReport.DoesNotExist:
                daily_report = None

        return {
            "id": str(report_run.id),
            "status": report_run.status,
            "store_id": str(report_run.store_id),
            "created_at": cls._format_datetime(report_run.created_at),
            "updated_at": cls._format_datetime(report_run.updated_at),
            "generated_at": cls._format_datetime(daily_report.generated_at)
            if daily_report
            else None,
            "summary": cls._report_summary(report_run, daily_report),
            "error_message": report_run.error_message if report_run.status == "failed" else "",
            "coordinator": cls._coordinator_metadata(daily_report),
        }

    @classmethod
    def serialize_report_run_detail(cls, report_run: ReportRun) -> dict[str, Any]:
        data = cls.serialize_report_run_summary(report_run)
        daily_report = getattr(report_run, "daily_report", None)
        if daily_report is None:
            try:
                daily_report = report_run.daily_report
            except DailyReport.DoesNotExist:
                daily_report = None

        data["daily_report"] = cls._serialize_daily_report(daily_report)
        data["counts"] = {
            "agent_outputs": report_run.agent_outputs.count(),
            "actions": report_run.actions.count(),
        }
        return data

    @staticmethod
    def _report_summary(
        report_run: ReportRun,
        daily_report: DailyReport | None,
    ) -> str:
        if report_run.status == "failed":
            return "The daily report run failed."
        if daily_report is not None:
            content = daily_report.content if isinstance(daily_report.content, dict) else {}
            insights = content.get("operational_insights") or []
            if insights and isinstance(insights[0], str):
                return insights[0]
            return "Daily report is available for review."
        if report_run.status == "completed":
            return "The daily report run completed successfully."
        if report_run.status == "running":
            return "The daily report run is in progress."
        return "A daily report run was queued."

    @staticmethod
    def _coordinator_metadata(daily_report: DailyReport | None) -> dict[str, Any]:
        if daily_report is None:
            return {
                "agent_name": "coordinator-agent",
                "has_daily_report": False,
                "daily_report_id": None,
            }
        return {
            "agent_name": "coordinator-agent",
            "has_daily_report": True,
            "daily_report_id": str(daily_report.id),
        }

    @classmethod
    def _serialize_daily_report(cls, daily_report: DailyReport | None) -> dict[str, Any] | None:
        if daily_report is None:
            return None

        content = daily_report.content if isinstance(daily_report.content, dict) else {}
        return {
            "id": str(daily_report.id),
            "generated_at": cls._format_datetime(daily_report.generated_at),
            "sections": {
                "operational_insights": cls._section_preview(content.get("operational_insights")),
                "prioritized_actions": cls._section_count(content.get("prioritized_actions")),
                "content_suggestions": cls._section_count(content.get("content_suggestions")),
                "support_insights": cls._section_count(content.get("support_insights")),
                "next_steps": cls._section_count(content.get("next_steps")),
            },
            "period": content.get("period") if isinstance(content.get("period"), dict) else None,
        }

    @staticmethod
    def _section_preview(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        preview: list[str] = []
        for item in value[:3]:
            if isinstance(item, str):
                preview.append(item)
        return preview

    @staticmethod
    def _section_count(value: Any) -> int:
        return len(value) if isinstance(value, list) else 0

    @classmethod
    def _paginate_queryset(
        cls,
        queryset,
        *,
        serializer,
        pagination: dict[str, Any],
        request=None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filters = filters or {}
        limit = pagination.get("limit", DEFAULT_HISTORY_LIMIT)
        offset = pagination.get("offset", 0)
        total = queryset.count()
        page = queryset[offset : offset + limit]
        results = [serializer(item) for item in page]
        return {
            "count": total,
            "next": cls._build_page_url(
                offset=offset + limit,
                limit=limit,
                filters={},
                request=request,
                has_more=offset + limit < total,
            ),
            "previous": cls._build_page_url(
                offset=max(0, offset - limit),
                limit=limit,
                filters={},
                request=request,
                has_more=offset > 0,
            ),
            "results": results,
        }

    @classmethod
    def _build_page_url(
        cls,
        *,
        offset: int,
        limit: int,
        filters: dict[str, Any],
        request,
        has_more: bool,
    ) -> str | None:
        if not has_more:
            return None

        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for key, value in filters.items():
            if value is None:
                continue
            if isinstance(value, datetime):
                if timezone.is_naive(value):
                    value = timezone.make_aware(value)
                params[key] = value.isoformat().replace("+00:00", "Z")
            else:
                params[key] = str(value)

        query_string = urlencode(params)
        if request is not None:
            base_path = request.build_absolute_uri(request.path)
            return f"{base_path}?{query_string}"
        return f"?{query_string}"

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        if timezone.is_naive(value):
            value = timezone.make_aware(value)
        return value.isoformat().replace("+00:00", "Z")


class DashboardActionService:
    @classmethod
    def list_for_user(
        cls,
        *,
        user: User,
        filters: dict[str, Any] | None = None,
        pagination: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        filters = filters or {}
        pagination = pagination or {}

        queryset = DashboardScopeService.scoped_actions(user)

        status = filters.get("status")
        if status:
            queryset = queryset.filter(status=status)

        action_type = filters.get("action_type")
        if action_type:
            queryset = queryset.filter(action_type=action_type)

        agent_name = filters.get("agent_name")
        if agent_name:
            queryset = queryset.filter(agent_name=agent_name)

        requires_approval = filters.get("requires_approval")
        if requires_approval is not None:
            queryset = queryset.filter(requires_approval=requires_approval)

        from_timestamp = filters.get("from_timestamp")
        if from_timestamp:
            queryset = queryset.filter(created_at__gte=from_timestamp)

        to_timestamp = filters.get("to_timestamp")
        if to_timestamp:
            queryset = queryset.filter(created_at__lte=to_timestamp)

        queryset = queryset.order_by("-created_at")

        url_filters = cls._build_url_filters(filters)

        return DashboardReportService._paginate_queryset(
            queryset,
            serializer=cls.serialize_action,
            pagination=pagination,
            request=request,
            filters=url_filters,
        )

    @staticmethod
    def _build_url_filters(filters: dict[str, Any]) -> dict[str, Any]:
        url_filters: dict[str, Any] = {}
        for key in ("status", "action_type", "agent_name", "requires_approval"):
            value = filters.get(key)
            if value is not None:
                url_filters[key] = value
        if filters.get("from_timestamp"):
            url_filters["from"] = filters["from_timestamp"]
        if filters.get("to_timestamp"):
            url_filters["to"] = filters["to_timestamp"]
        return url_filters

    @classmethod
    def serialize_action(cls, action: Action) -> dict[str, Any]:
        decided_by = None
        if action.decided_by_id is not None and action.decided_by is not None:
            decided_by = {
                "id": str(action.decided_by_id),
                "email": action.decided_by.email,
                "full_name": action.decided_by.full_name,
            }

        return {
            "id": str(action.id),
            "action_type": action.action_type,
            "title": action.title,
            "description": action.description,
            "status": action.status,
            "status_reason": action.status_reason,
            "priority": action.priority,
            "requires_approval": action.requires_approval,
            "agent_name": action.agent_name,
            "report_run_id": str(action.report_run_id) if action.report_run_id else None,
            "store_id": str(action.store_id),
            "created_at": DashboardReportService._format_datetime(action.created_at),
            "updated_at": DashboardReportService._format_datetime(action.updated_at),
            "decided_by": decided_by,
            "decided_at": DashboardReportService._format_datetime(action.decided_at),
            "payload_summary": build_safe_payload_summary(action.payload),
        }


def build_safe_payload_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    summary: dict[str, Any] = {}
    for key, value in payload.items():
        if key in SENSITIVE_PAYLOAD_KEYS:
            continue
        if key in SAFE_PAYLOAD_KEYS:
            if isinstance(value, str) and len(value) > 120:
                summary[key] = f"{value[:117]}..."
            else:
                summary[key] = value
    return summary


class DashboardPaginationDefaults:
    DEFAULT_LIMIT = DEFAULT_HISTORY_LIMIT
    MAX_LIMIT = MAX_HISTORY_LIMIT
