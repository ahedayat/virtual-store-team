from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from django.utils import timezone

from accounts.models import User
from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_EVENT_TYPE_QUEUED,
    ACTION_EVENT_TYPE_REJECTED,
    REPORT_RUN_STATUS_QUEUED,
)
from operations.history_constants import (
    HISTORY_TYPE_ACTION_CREATED,
    HISTORY_TYPE_ACTION_EVENT,
    HISTORY_TYPE_AGENT_OUTPUT_CREATED,
    HISTORY_TYPE_DAILY_REPORT_CREATED,
    REPORT_RUN_STATUS_TO_HISTORY_TYPE,
)
from operations.models import (
    Action,
    ActionEvent,
    ActionEventActorType,
    AgentOutput,
    DailyReport,
    ReportRun,
)
from stores.models import Store
from tenants.models import Tenant


class HistoryFeedService:
    @classmethod
    def list_for_user(
        cls,
        *,
        user: User,
        filters: dict[str, Any] | None = None,
        pagination: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        tenant, store = cls._resolve_scope(user)
        filters = filters or {}
        pagination = pagination or {}

        items = cls.build_feed(tenant=tenant, store=store)
        items = cls._apply_filters(items, filters)
        items.sort(key=lambda item: item["timestamp"], reverse=True)

        limit = pagination.get("limit", 20)
        offset = pagination.get("offset", 0)
        return cls._paginate(items, limit=limit, offset=offset, filters=filters, request=request)

    @classmethod
    def build_feed(
        cls,
        *,
        tenant: Tenant,
        store: Store | None = None,
    ) -> list[dict[str, Any]]:
        report_runs = cls._scoped_report_runs(tenant, store)
        daily_reports = cls._scoped_daily_reports(tenant, store)
        agent_outputs = cls._scoped_agent_outputs(tenant, store)
        actions = cls._scoped_actions(tenant, store)
        action_events = cls._scoped_action_events(tenant, store)

        items: list[dict[str, Any]] = []
        items.extend(cls._normalize_report_runs(report_runs))
        items.extend(cls._normalize_daily_reports(daily_reports))
        items.extend(cls._normalize_agent_outputs(agent_outputs))
        items.extend(cls._normalize_actions(actions))
        items.extend(cls._normalize_action_events(action_events))
        return items

    @staticmethod
    def _resolve_scope(user: User) -> tuple[Tenant, Store | None]:
        tenant = user.tenant
        store = user.store
        return tenant, store

    @staticmethod
    def _scoped_report_runs(tenant: Tenant, store: Store | None):
        queryset = ReportRun.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("store")

    @staticmethod
    def _scoped_daily_reports(tenant: Tenant, store: Store | None):
        queryset = DailyReport.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("report_run", "store")

    @staticmethod
    def _scoped_agent_outputs(tenant: Tenant, store: Store | None):
        queryset = AgentOutput.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("report_run", "store")

    @staticmethod
    def _scoped_actions(tenant: Tenant, store: Store | None):
        queryset = Action.objects.filter(tenant=tenant)
        if store is not None:
            queryset = queryset.filter(store=store)
        return queryset.select_related("report_run", "store")

    @staticmethod
    def _scoped_action_events(tenant: Tenant, store: Store | None):
        queryset = ActionEvent.objects.filter(action__tenant=tenant)
        if store is not None:
            queryset = queryset.filter(action__store=store)
        return queryset.select_related("action", "action__report_run").order_by("created_at")

    @classmethod
    def _normalize_report_runs(cls, report_runs) -> list[dict[str, Any]]:
        items = []
        for report_run in report_runs:
            item_type = REPORT_RUN_STATUS_TO_HISTORY_TYPE.get(report_run.status)
            if item_type is None:
                continue

            timestamp = cls._report_run_timestamp(report_run)
            summary = cls._report_run_summary(report_run)
            metadata: dict[str, Any] = {"report_run_status": report_run.status}
            if report_run.status == "failed" and report_run.error_message:
                metadata["has_error"] = True

            items.append(
                {
                    "id": f"report_run:{report_run.id}",
                    "type": item_type,
                    "title": cls._report_run_title(report_run.status),
                    "summary": summary,
                    "timestamp": timestamp,
                    "status": report_run.status,
                    "source": "system",
                    "agent_name": None,
                    "report_run_id": str(report_run.id),
                    "daily_report_id": None,
                    "action_id": None,
                    "metadata": metadata,
                }
            )
        return items

    @classmethod
    def _normalize_daily_reports(cls, daily_reports) -> list[dict[str, Any]]:
        items = []
        for daily_report in daily_reports:
            timestamp = daily_report.generated_at or daily_report.created_at
            metadata: dict[str, Any] = {}
            content = daily_report.content if isinstance(daily_report.content, dict) else {}
            if content.get("operational_insights"):
                metadata["operational_insight_count"] = len(content["operational_insights"])
            if content.get("prioritized_actions"):
                metadata["prioritized_action_count"] = len(content["prioritized_actions"])

            items.append(
                {
                    "id": f"daily_report:{daily_report.id}",
                    "type": HISTORY_TYPE_DAILY_REPORT_CREATED,
                    "title": "Daily report created",
                    "summary": "A daily report was generated for the store.",
                    "timestamp": timestamp,
                    "status": "completed",
                    "source": "coordinator-agent",
                    "agent_name": "coordinator-agent",
                    "report_run_id": str(daily_report.report_run_id),
                    "daily_report_id": str(daily_report.id),
                    "action_id": None,
                    "metadata": metadata,
                }
            )
        return items

    @classmethod
    def _normalize_agent_outputs(cls, agent_outputs) -> list[dict[str, Any]]:
        items = []
        for agent_output in agent_outputs:
            output = agent_output.output if isinstance(agent_output.output, dict) else {}
            output_type = output.get("output_type", "agent_output")
            metadata: dict[str, Any] = {"output_type": output_type}
            if output.get("metadata") and isinstance(output["metadata"], dict):
                safe_keys = ("version", "duration_ms", "model_id")
                for key in safe_keys:
                    if key in output["metadata"]:
                        metadata[key] = output["metadata"][key]

            report_run_id = (
                str(agent_output.report_run_id) if agent_output.report_run_id else None
            )
            items.append(
                {
                    "id": f"agent_output:{agent_output.id}",
                    "type": HISTORY_TYPE_AGENT_OUTPUT_CREATED,
                    "title": f"{agent_output.agent_name} output recorded",
                    "summary": f"Structured {output_type} output from {agent_output.agent_name}.",
                    "timestamp": agent_output.created_at,
                    "status": "created",
                    "source": "agent",
                    "agent_name": agent_output.agent_name,
                    "report_run_id": report_run_id,
                    "daily_report_id": None,
                    "action_id": None,
                    "metadata": metadata,
                }
            )
        return items

    @classmethod
    def _normalize_actions(cls, actions) -> list[dict[str, Any]]:
        items = []
        for action in actions:
            report_run_id = str(action.report_run_id) if action.report_run_id else None
            items.append(
                {
                    "id": f"action:{action.id}",
                    "type": HISTORY_TYPE_ACTION_CREATED,
                    "title": action.title,
                    "summary": action.description,
                    "timestamp": action.created_at,
                    "status": action.status,
                    "source": "agent",
                    "agent_name": action.agent_name,
                    "report_run_id": report_run_id,
                    "daily_report_id": None,
                    "action_id": str(action.id),
                    "metadata": {
                        "action_type": action.action_type,
                        "priority": action.priority,
                        "requires_approval": action.requires_approval,
                    },
                }
            )
        return items

    @classmethod
    def _normalize_action_events(cls, action_events) -> list[dict[str, Any]]:
        items = []
        for event in action_events:
            action = event.action
            report_run_id = str(action.report_run_id) if action.report_run_id else None
            items.append(
                {
                    "id": f"action_event:{event.id}",
                    "type": HISTORY_TYPE_ACTION_EVENT,
                    "title": cls._action_event_title(event.event_type),
                    "summary": cls._action_event_summary(event, action),
                    "timestamp": event.created_at,
                    "status": event.new_status,
                    "source": cls._actor_source(event.actor_type),
                    "agent_name": action.agent_name,
                    "report_run_id": report_run_id,
                    "daily_report_id": None,
                    "action_id": str(action.id),
                    "metadata": {
                        "event_type": event.event_type,
                        "action_type": action.action_type,
                        "priority": action.priority,
                        "previous_status": event.previous_status or None,
                    },
                }
            )
        return items

    @staticmethod
    def _report_run_timestamp(report_run: ReportRun) -> datetime:
        if report_run.status == REPORT_RUN_STATUS_QUEUED:
            return report_run.created_at
        return report_run.updated_at

    @staticmethod
    def _report_run_title(status: str) -> str:
        titles = {
            "queued": "Report run queued",
            "running": "Report run running",
            "completed": "Report run completed",
            "failed": "Report run failed",
        }
        return titles.get(status, f"Report run {status}")

    @staticmethod
    def _report_run_summary(report_run: ReportRun) -> str:
        if report_run.status == "failed":
            return "The daily report run failed."
        if report_run.status == "completed":
            return "The daily report run completed successfully."
        if report_run.status == "running":
            return "The daily report run is in progress."
        return "A daily report run was queued."

    @staticmethod
    def _action_event_title(event_type: str) -> str:
        titles = {
            ACTION_EVENT_TYPE_CREATED: "Action created",
            ACTION_EVENT_TYPE_APPROVED: "Action approved",
            ACTION_EVENT_TYPE_REJECTED: "Action rejected",
            ACTION_EVENT_TYPE_QUEUED: "Action queued for execution",
        }
        return titles.get(event_type, f"Action {event_type}")

    @staticmethod
    def _action_event_summary(event: ActionEvent, action: Action) -> str:
        if event.reason:
            return event.reason
        if event.event_type == ACTION_EVENT_TYPE_APPROVED:
            return f"Manager approved {action.title}."
        if event.event_type == ACTION_EVENT_TYPE_REJECTED:
            return f"Manager rejected {action.title}."
        if event.event_type == ACTION_EVENT_TYPE_QUEUED:
            return f"{action.title} was queued for execution."
        return action.description

    @staticmethod
    def _actor_source(actor_type: str) -> str:
        if actor_type == ActionEventActorType.USER:
            return "manager"
        if actor_type == ActionEventActorType.AGENT:
            return "agent"
        return "system"

    @classmethod
    def _apply_filters(cls, items: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict]:
        filtered = items

        item_type = filters.get("type")
        if item_type:
            filtered = [item for item in filtered if item["type"] == item_type]

        status = filters.get("status")
        if status:
            filtered = [item for item in filtered if item.get("status") == status]

        agent_name = filters.get("agent_name")
        if agent_name:
            filtered = [
                item for item in filtered if item.get("agent_name") == agent_name
            ]

        report_run_id = filters.get("report_run_id")
        if report_run_id:
            report_run_id_str = str(report_run_id)
            filtered = [
                item
                for item in filtered
                if item.get("report_run_id") == report_run_id_str
            ]

        action_id = filters.get("action_id")
        if action_id:
            action_id_str = str(action_id)
            filtered = [
                item
                for item in filtered
                if item.get("action_id") == action_id_str
            ]

        from_timestamp = filters.get("from_timestamp")
        if from_timestamp:
            if timezone.is_naive(from_timestamp):
                from_timestamp = timezone.make_aware(from_timestamp)
            filtered = [item for item in filtered if item["timestamp"] >= from_timestamp]

        to_timestamp = filters.get("to_timestamp")
        if to_timestamp:
            if timezone.is_naive(to_timestamp):
                to_timestamp = timezone.make_aware(to_timestamp)
            filtered = [item for item in filtered if item["timestamp"] <= to_timestamp]

        return filtered

    @classmethod
    def _paginate(
        cls,
        items: list[dict[str, Any]],
        *,
        limit: int,
        offset: int,
        filters: dict[str, Any],
        request=None,
    ) -> dict[str, Any]:
        total = len(items)
        page_items = items[offset : offset + limit]
        serialized_results = [cls._serialize_item(item) for item in page_items]

        return {
            "count": total,
            "next": cls._build_page_url(
                offset=offset + limit,
                limit=limit,
                filters=filters,
                request=request,
                has_more=offset + limit < total,
            ),
            "previous": cls._build_page_url(
                offset=max(0, offset - limit),
                limit=limit,
                filters=filters,
                request=request,
                has_more=offset > 0,
            ),
            "results": serialized_results,
        }

    @staticmethod
    def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
        serialized = dict(item)
        timestamp = serialized.get("timestamp")
        if isinstance(timestamp, datetime):
            if timezone.is_naive(timestamp):
                timestamp = timezone.make_aware(timestamp)
            serialized["timestamp"] = timestamp.isoformat().replace("+00:00", "Z")
        return serialized

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
        for key, query_key in (
            ("type", "type"),
            ("status", "status"),
            ("agent_name", "agent_name"),
            ("report_run_id", "report_run_id"),
            ("action_id", "action_id"),
            ("from_timestamp", "from"),
            ("to_timestamp", "to"),
        ):
            value = filters.get(key)
            if value is None:
                continue
            if isinstance(value, datetime):
                if timezone.is_naive(value):
                    value = timezone.make_aware(value)
                params[query_key] = value.isoformat().replace("+00:00", "Z")
            else:
                params[query_key] = str(value)

        query_string = urlencode(params)
        if request is not None:
            base_path = request.build_absolute_uri(request.path)
            return f"{base_path}?{query_string}"
        return f"?{query_string}"
