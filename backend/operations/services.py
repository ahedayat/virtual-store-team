from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.constants import AI_SERVICE_COORDINATOR
from accounts.models import User, UserRole
from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_EVENT_TYPE_EXECUTED,
    ACTION_EVENT_TYPE_EXECUTING,
    ACTION_EVENT_TYPE_QUEUED,
    ACTION_EVENT_TYPE_REJECTED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_CANCELLED,
    ACTION_STATUS_EXECUTED,
    ACTION_STATUS_EXECUTING,
    ACTION_STATUS_FAILED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_STATUS_REJECTED,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
    ALLOWED_AGENT_NAMES,
    DEFAULT_REQUIRES_APPROVAL_BY_ACTION_TYPE,
    MAX_ACTION_PRIORITY,
    MIN_ACTION_PRIORITY,
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
    REPORT_RUN_ACTIVE_STATUSES,
    REPORT_RUN_TERMINAL_STATUSES,
    SUPPORTED_ACTION_TYPES,
)
from operations.exceptions import (
    ActionPayloadValidationError,
    ActionScopeError,
    ActionTransitionError,
    AgentOutputPayloadValidationError,
    AgentOutputScopeError,
    ReportRunPayloadValidationError,
    ReportRunPermissionError,
    ReportRunReferenceError,
    ReportRunScopeError,
    ReportRunTransitionError,
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


class ActionService:
    @classmethod
    def create_from_agent_payload(
        cls,
        *,
        tenant: Tenant,
        store: Store,
        agent_name: str,
        payload: dict[str, Any],
        report_run=None,
        source_agent_output: AgentOutput | None = None,
    ) -> Action:
        cls._validate_scope(
            tenant=tenant,
            store=store,
            report_run=report_run,
            source_agent_output=source_agent_output,
        )
        normalized = cls._validate_and_normalize_payload(payload)
        cls._validate_agent_name(agent_name)

        action_type = normalized["action_type"]
        action_payload = normalized["payload"]
        requires_approval = cls._resolve_requires_approval(
            action_type=action_type,
            explicit_requires_approval=normalized["requires_approval"],
            action_payload=action_payload,
            outer_payload=payload,
        )
        initial_status = (
            ACTION_STATUS_PENDING_APPROVAL
            if requires_approval
            else ACTION_STATUS_QUEUED
        )
        status_reason = cls._build_initial_status_reason(
            action_type=action_type,
            requires_approval=requires_approval,
            explicit_requires_approval=normalized["requires_approval"],
            action_payload=action_payload,
        )

        with transaction.atomic():
            action = Action.objects.create(
                tenant=tenant,
                store=store,
                report_run=report_run,
                source_agent_output=source_agent_output,
                agent_name=agent_name,
                action_type=action_type,
                title=normalized["title"],
                description=normalized["description"],
                payload=action_payload,
                priority=normalized["priority"],
                requires_approval=requires_approval,
                status=initial_status,
                status_reason=status_reason,
            )
            ActionEvent.objects.create(
                action=action,
                event_type=ACTION_EVENT_TYPE_CREATED,
                previous_status="",
                new_status=initial_status,
                reason=status_reason,
                actor_type=ActionEventActorType.AGENT,
                actor_id=agent_name,
                metadata={
                    "action_type": action_type,
                    "requires_approval": requires_approval,
                    "policy_source": cls._policy_source_label(
                        action_type=action_type,
                        explicit_requires_approval=normalized["requires_approval"],
                        action_payload=action_payload,
                    ),
                },
            )

        return action

    @classmethod
    def approve(
        cls,
        *,
        action: Action,
        actor: User,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Action:
        cls._validate_human_decision_actor(action=action, actor=actor)
        return cls._transition_action(
            action=action,
            expected_current_status=ACTION_STATUS_PENDING_APPROVAL,
            new_status=ACTION_STATUS_APPROVED,
            event_type=ACTION_EVENT_TYPE_APPROVED,
            actor_type=ActionEventActorType.USER,
            actor_id=str(actor.id),
            reason=reason,
            metadata=metadata,
            field_updates=cls._build_decision_field_updates(actor=actor, reason=reason),
        )

    @classmethod
    def reject(
        cls,
        *,
        action: Action,
        actor: User,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Action:
        cls._validate_human_decision_actor(action=action, actor=actor)
        return cls._transition_action(
            action=action,
            expected_current_status=ACTION_STATUS_PENDING_APPROVAL,
            new_status=ACTION_STATUS_REJECTED,
            event_type=ACTION_EVENT_TYPE_REJECTED,
            actor_type=ActionEventActorType.USER,
            actor_id=str(actor.id),
            reason=reason,
            metadata=metadata,
            field_updates=cls._build_decision_field_updates(actor=actor, reason=reason),
        )

    @classmethod
    def queue_execution(
        cls,
        *,
        action: Action,
        actor: User | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Action:
        if actor is not None:
            if not isinstance(actor, User):
                raise ActionTransitionError(
                    "queue_execution actor must be a human user when provided."
                )
            if actor.tenant_id != action.tenant_id:
                raise ActionTransitionError(
                    "Actor must belong to the same tenant as the action."
                )

        actor_type, actor_id = cls._resolve_transition_actor(actor)
        return cls._transition_action(
            action=action,
            expected_current_status=ACTION_STATUS_APPROVED,
            new_status=ACTION_STATUS_QUEUED,
            event_type=ACTION_EVENT_TYPE_QUEUED,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            metadata=metadata,
            field_updates={},
        )

    @staticmethod
    def _validate_human_decision_actor(*, action: Action, actor: User) -> None:
        if not isinstance(actor, User):
            raise ActionTransitionError(
                "Approval and rejection require a trusted human user actor."
            )
        if actor.tenant_id != action.tenant_id:
            raise ActionTransitionError(
                "Actor must belong to the same tenant as the action."
            )
        if actor.role != UserRole.MANAGER and not actor.is_staff:
            raise ActionTransitionError(
                "Only managers or staff users can approve or reject actions."
            )

    @staticmethod
    def _build_decision_field_updates(*, actor: User, reason: str | None) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "decided_by": actor,
            "decided_at": timezone.now(),
        }
        if reason is not None:
            updates["status_reason"] = reason
        return updates

    @staticmethod
    def _resolve_transition_actor(actor: User | None) -> tuple[str, str]:
        if actor is None:
            return ActionEventActorType.SYSTEM, "system"
        return ActionEventActorType.USER, str(actor.id)

    @classmethod
    def _transition_action(
        cls,
        *,
        action: Action,
        expected_current_status: str,
        new_status: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        reason: str | None,
        metadata: dict[str, Any] | None,
        field_updates: dict[str, Any],
    ) -> Action:
        with transaction.atomic():
            locked_action = Action.objects.select_for_update().get(pk=action.pk)
            current_status = locked_action.status

            if current_status != expected_current_status:
                raise ActionTransitionError(
                    cls._transition_error_message(
                        attempted=event_type,
                        current_status=current_status,
                        expected_status=expected_current_status,
                    )
                )

            locked_action.status = new_status
            for field_name, field_value in field_updates.items():
                setattr(locked_action, field_name, field_value)

            update_field_names = ["status", "updated_at", *field_updates.keys()]
            locked_action.save(update_fields=update_field_names)

            event_metadata = dict(metadata or {})
            ActionEvent.objects.create(
                action=locked_action,
                event_type=event_type,
                previous_status=current_status,
                new_status=new_status,
                reason=reason or "",
                actor_type=actor_type,
                actor_id=actor_id,
                metadata=event_metadata,
            )

        locked_action.refresh_from_db()
        return locked_action

    @staticmethod
    def _transition_error_message(
        *,
        attempted: str,
        current_status: str,
        expected_status: str,
    ) -> str:
        return (
            f"Cannot perform {attempted} transition from status {current_status!r}; "
            f"expected {expected_status!r}."
        )

    @staticmethod
    def _validate_scope(
        *,
        tenant: Tenant,
        store: Store,
        report_run,
        source_agent_output: AgentOutput | None,
    ) -> None:
        if store.tenant_id != tenant.id:
            raise ActionScopeError("Store does not belong to the trusted tenant context.")

        if report_run is not None:
            if report_run.tenant_id != tenant.id or report_run.store_id != store.id:
                raise ActionScopeError(
                    "Report run does not belong to the trusted tenant/store context."
                )

        if source_agent_output is not None:
            if (
                source_agent_output.tenant_id != tenant.id
                or source_agent_output.store_id != store.id
            ):
                raise ActionScopeError(
                    "Agent output does not belong to the trusted tenant/store context."
                )

    @staticmethod
    def _validate_agent_name(agent_name: str) -> None:
        if agent_name not in ALLOWED_AGENT_NAMES:
            raise ActionPayloadValidationError(
                f"Unsupported agent_name: {agent_name!r}."
            )

    @classmethod
    def _validate_and_normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ActionPayloadValidationError("Payload must be a JSON object.")

        action_type = payload.get("action_type")
        if not action_type or not isinstance(action_type, str):
            raise ActionPayloadValidationError("action_type is required.")
        if action_type not in SUPPORTED_ACTION_TYPES:
            raise ActionPayloadValidationError(f"Unsupported action_type: {action_type!r}.")

        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ActionPayloadValidationError("title is required and must be non-empty.")

        description = payload.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ActionPayloadValidationError(
                "description is required and must be non-empty."
            )

        priority = payload.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ActionPayloadValidationError("priority must be an integer.")
        if priority < MIN_ACTION_PRIORITY or priority > MAX_ACTION_PRIORITY:
            raise ActionPayloadValidationError(
                f"priority must be between {MIN_ACTION_PRIORITY} and {MAX_ACTION_PRIORITY}."
            )

        action_payload = payload.get("payload", {})
        if action_payload is None:
            action_payload = {}
        if not isinstance(action_payload, dict):
            raise ActionPayloadValidationError("payload must be a JSON object.")

        explicit_requires_approval = payload.get("requires_approval")
        if explicit_requires_approval is not None and not isinstance(
            explicit_requires_approval, bool
        ):
            raise ActionPayloadValidationError("requires_approval must be a boolean when provided.")

        return {
            "action_type": action_type,
            "title": title.strip(),
            "description": description.strip(),
            "priority": priority,
            "payload": action_payload,
            "requires_approval": explicit_requires_approval,
        }

    @classmethod
    def _resolve_requires_approval(
        cls,
        *,
        action_type: str,
        explicit_requires_approval: bool | None,
        action_payload: dict[str, Any],
        outer_payload: dict[str, Any],
    ) -> bool:
        if explicit_requires_approval is not None:
            if (
                action_type == ACTION_TYPE_SUPPORT_REPLY_DRAFT
                and explicit_requires_approval is False
                and not cls._is_low_risk(action_payload, outer_payload)
            ):
                return True
            return explicit_requires_approval

        if action_type == ACTION_TYPE_SUPPORT_REPLY_DRAFT and cls._is_low_risk(
            action_payload, outer_payload
        ):
            return False

        return DEFAULT_REQUIRES_APPROVAL_BY_ACTION_TYPE[action_type]

    @staticmethod
    def _is_low_risk(action_payload: dict[str, Any], outer_payload: dict[str, Any]) -> bool:
        if outer_payload.get("low_risk") is True:
            return True
        return action_payload.get("low_risk") is True

    @classmethod
    def _build_initial_status_reason(
        cls,
        *,
        action_type: str,
        requires_approval: bool,
        explicit_requires_approval: bool | None,
        action_payload: dict[str, Any],
    ) -> str:
        if requires_approval:
            if explicit_requires_approval is True:
                return "Action requires manager approval (explicit agent flag)."
            if (
                action_type == ACTION_TYPE_SUPPORT_REPLY_DRAFT
                and explicit_requires_approval is False
            ):
                return (
                    "Action requires manager approval (support.reply_draft is not low risk)."
                )
            return f"Action requires manager approval (default policy for {action_type})."

        if action_type == ACTION_TYPE_SUPPORT_REPLY_DRAFT:
            return "Action queued by policy (low-risk support.reply_draft)."
        if explicit_requires_approval is False:
            return "Action queued by policy (explicit auto-executable flag)."
        return f"Action queued by default policy for {action_type}."

    @classmethod
    def _policy_source_label(
        cls,
        *,
        action_type: str,
        explicit_requires_approval: bool | None,
        action_payload: dict[str, Any],
    ) -> str:
        if explicit_requires_approval is not None:
            return "explicit_requires_approval"
        if action_type == ACTION_TYPE_SUPPORT_REPLY_DRAFT and action_payload.get(
            "low_risk"
        ) is True:
            return "low_risk_payload"
        return "default_action_type_policy"

    @classmethod
    def execute_stub(cls, *, action: Action) -> dict[str, Any]:
        """MVP stub execution for queued actions with no external side effects."""
        terminal_skip_statuses = {
            ACTION_STATUS_FAILED,
            ACTION_STATUS_REJECTED,
            ACTION_STATUS_CANCELLED,
        }

        with transaction.atomic():
            locked_action = Action.objects.select_for_update().get(pk=action.pk)
            current_status = locked_action.status

            if current_status == ACTION_STATUS_EXECUTED:
                return {
                    "outcome": "already_executed",
                    "action_id": str(locked_action.id),
                    "status": locked_action.status,
                }
            if current_status in terminal_skip_statuses:
                return {
                    "outcome": "terminal_skip",
                    "action_id": str(locked_action.id),
                    "status": current_status,
                }
            if current_status == ACTION_STATUS_EXECUTING:
                return {
                    "outcome": "already_executing",
                    "action_id": str(locked_action.id),
                    "status": current_status,
                }
            if current_status != ACTION_STATUS_QUEUED:
                return {
                    "outcome": "not_executable",
                    "action_id": str(locked_action.id),
                    "status": current_status,
                }

            locked_action.status = ACTION_STATUS_EXECUTING
            locked_action.save(update_fields=["status", "updated_at"])
            ActionEvent.objects.create(
                action=locked_action,
                event_type=ACTION_EVENT_TYPE_EXECUTING,
                previous_status=ACTION_STATUS_QUEUED,
                new_status=ACTION_STATUS_EXECUTING,
                reason="Action execution started by Celery worker.",
                actor_type=ActionEventActorType.SYSTEM,
                actor_id="system",
                metadata={"execution_mode": "stub"},
            )

            execution_result = {
                "outcome": "stubbed",
                "action_type": locked_action.action_type,
                "message": (
                    "MVP stub execution completed without external side effects."
                ),
            }
            executed_at = timezone.now()
            locked_action.status = ACTION_STATUS_EXECUTED
            locked_action.executed_at = executed_at
            locked_action.execution_result = execution_result
            locked_action.save(
                update_fields=[
                    "status",
                    "executed_at",
                    "execution_result",
                    "updated_at",
                ]
            )
            ActionEvent.objects.create(
                action=locked_action,
                event_type=ACTION_EVENT_TYPE_EXECUTED,
                previous_status=ACTION_STATUS_EXECUTING,
                new_status=ACTION_STATUS_EXECUTED,
                reason="Action stub execution completed.",
                actor_type=ActionEventActorType.SYSTEM,
                actor_id="system",
                metadata={"execution_mode": "stub"},
            )

        return {
            "outcome": "executed",
            "action_id": str(locked_action.id),
            "status": ACTION_STATUS_EXECUTED,
            "execution_result": execution_result,
        }


class AgentOutputService:
    @classmethod
    def create_from_agent_payload(
        cls,
        *,
        tenant: Tenant,
        store: Store,
        agent_name: str,
        output_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        report_run: ReportRun | None = None,
    ) -> AgentOutput:
        cls._validate_scope(tenant=tenant, store=store, report_run=report_run)
        cls._validate_agent_name(agent_name)
        normalized = cls._validate_and_normalize_payload(
            output_type=output_type,
            payload=payload,
            metadata=metadata,
        )

        output_data = {
            "output_type": normalized["output_type"],
            "payload": normalized["payload"],
        }
        if normalized["metadata"]:
            output_data["metadata"] = normalized["metadata"]

        return AgentOutput.objects.create(
            tenant=tenant,
            store=store,
            report_run=report_run,
            agent_name=agent_name,
            output=output_data,
        )

    @staticmethod
    def _validate_scope(
        *,
        tenant: Tenant,
        store: Store,
        report_run: ReportRun | None,
    ) -> None:
        if store.tenant_id != tenant.id:
            raise AgentOutputScopeError("Store does not belong to the trusted tenant context.")

        if report_run is not None:
            if report_run.tenant_id != tenant.id or report_run.store_id != store.id:
                raise AgentOutputScopeError(
                    "Report run does not belong to the trusted tenant/store context."
                )

    @staticmethod
    def _validate_agent_name(agent_name: str) -> None:
        if agent_name not in ALLOWED_AGENT_NAMES:
            raise AgentOutputPayloadValidationError(
                f"Unsupported agent_name: {agent_name!r}."
            )

    @staticmethod
    def _validate_and_normalize_payload(
        *,
        output_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(output_type, str) or not output_type.strip():
            raise AgentOutputPayloadValidationError(
                "output_type is required and must be non-empty."
            )

        if not isinstance(payload, dict):
            raise AgentOutputPayloadValidationError("payload must be a JSON object.")

        normalized_metadata = metadata or {}
        if not isinstance(normalized_metadata, dict):
            raise AgentOutputPayloadValidationError("metadata must be a JSON object.")

        return {
            "output_type": output_type.strip(),
            "payload": payload,
            "metadata": normalized_metadata,
        }


@dataclass(frozen=True)
class CreateQueuedRunResult:
    created: bool
    report_run: ReportRun


class ReportRunService:
    @staticmethod
    def is_active(report_run: ReportRun) -> bool:
        return report_run.status in REPORT_RUN_ACTIVE_STATUSES

    @staticmethod
    def is_terminal(report_run: ReportRun) -> bool:
        return report_run.status in REPORT_RUN_TERMINAL_STATUSES

    @classmethod
    def get_active_run_for_store(cls, *, tenant: Tenant, store: Store) -> ReportRun | None:
        if store.tenant_id != tenant.id:
            raise ReportRunScopeError("Store does not belong to the trusted tenant context.")
        return (
            ReportRun.objects.filter(
                tenant=tenant,
                store=store,
                status__in=REPORT_RUN_ACTIVE_STATUSES,
            )
            .order_by("-created_at")
            .first()
        )

    @classmethod
    def create_queued_run_for_store(
        cls,
        *,
        tenant: Tenant,
        store: Store,
    ) -> CreateQueuedRunResult:
        if store.tenant_id != tenant.id:
            raise ReportRunScopeError("Store does not belong to the trusted tenant context.")

        with transaction.atomic():
            existing = cls.get_active_run_for_store(tenant=tenant, store=store)
            if existing is not None:
                return CreateQueuedRunResult(created=False, report_run=existing)

            try:
                report_run = ReportRun.objects.create(
                    tenant=tenant,
                    store=store,
                    status=REPORT_RUN_STATUS_QUEUED,
                )
            except IntegrityError:
                existing = cls.get_active_run_for_store(tenant=tenant, store=store)
                if existing is not None:
                    return CreateQueuedRunResult(created=False, report_run=existing)
                raise

        return CreateQueuedRunResult(created=True, report_run=report_run)

    @classmethod
    def mark_running(cls, *, report_run: ReportRun) -> ReportRun:
        with transaction.atomic():
            locked_report_run = ReportRun.objects.select_for_update().get(pk=report_run.pk)
            if locked_report_run.status in REPORT_RUN_TERMINAL_STATUSES:
                return locked_report_run
            if locked_report_run.status == REPORT_RUN_STATUS_QUEUED:
                locked_report_run.status = REPORT_RUN_STATUS_RUNNING
                locked_report_run.error_message = ""
                locked_report_run.save(
                    update_fields=["status", "error_message", "updated_at"]
                )
        locked_report_run.refresh_from_db()
        return locked_report_run

    @classmethod
    def mark_failed(cls, *, report_run: ReportRun, error_message: str) -> ReportRun:
        safe_message = (error_message or "Coordinator request failed.").strip()
        with transaction.atomic():
            locked_report_run = ReportRun.objects.select_for_update().get(pk=report_run.pk)
            if locked_report_run.status in REPORT_RUN_TERMINAL_STATUSES:
                return locked_report_run
            locked_report_run.status = REPORT_RUN_STATUS_FAILED
            locked_report_run.error_message = safe_message[:2000]
            locked_report_run.save(
                update_fields=["status", "error_message", "updated_at"]
            )
        locked_report_run.refresh_from_db()
        return locked_report_run

    @classmethod
    def mark_completed_if_still_running(cls, *, report_run: ReportRun) -> ReportRun:
        """Legacy skeleton completion helper; not used by coordinator-driven Celery flow."""
        with transaction.atomic():
            locked_report_run = ReportRun.objects.select_for_update().get(pk=report_run.pk)
            if locked_report_run.status != REPORT_RUN_STATUS_RUNNING:
                return locked_report_run
            locked_report_run.status = REPORT_RUN_STATUS_COMPLETED
            locked_report_run.error_message = ""
            locked_report_run.save(
                update_fields=["status", "error_message", "updated_at"]
            )
        locked_report_run.refresh_from_db()
        return locked_report_run

    @classmethod
    def cleanup_stale_active_runs(
        cls,
        *,
        stale_timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        timeout_seconds = (
            stale_timeout_seconds
            if stale_timeout_seconds is not None
            else settings.REPORT_RUN_STALE_TIMEOUT_SECONDS
        )
        cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
        error_message = (
            "Report run marked failed by stale-run cleanup after exceeding "
            f"the configured timeout ({timeout_seconds}s)."
        )

        stale_runs = ReportRun.objects.filter(
            status__in=REPORT_RUN_ACTIVE_STATUSES,
            updated_at__lt=cutoff,
        ).order_by("updated_at")

        marked_failed_ids: list[str] = []
        for report_run in stale_runs:
            marked = cls.mark_failed(
                report_run=report_run,
                error_message=error_message,
            )
            if marked.status == REPORT_RUN_STATUS_FAILED:
                marked_failed_ids.append(str(marked.id))

        return {
            "marked_failed_count": len(marked_failed_ids),
            "marked_failed_ids": marked_failed_ids,
            "stale_timeout_seconds": timeout_seconds,
        }

    @classmethod
    def complete_from_ai_payload(
        cls,
        *,
        report_run: ReportRun,
        tenant: Tenant,
        store: Store,
        service_name: str,
        report_payload: dict[str, Any],
        agent_output_ids: list | None = None,
        action_ids: list | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DailyReport:
        cls._validate_coordinator_service(service_name)
        cls._validate_scope(report_run=report_run, tenant=tenant, store=store)
        normalized_report = cls._validate_and_normalize_report_payload(report_payload)
        normalized_metadata = cls._validate_metadata(metadata)
        generated_at = normalized_report["generated_at"]
        content = dict(report_payload)
        if normalized_metadata:
            content["metadata"] = normalized_metadata

        with transaction.atomic():
            locked_report_run = ReportRun.objects.select_for_update().get(pk=report_run.pk)
            cls._validate_completable_status(locked_report_run)

            cls._validate_agent_output_ids(
                tenant=tenant,
                store=store,
                report_run=locked_report_run,
                agent_output_ids=agent_output_ids or [],
            )
            cls._validate_action_ids(
                tenant=tenant,
                store=store,
                report_run=locked_report_run,
                action_ids=action_ids or [],
            )

            daily_report = DailyReport.objects.create(
                tenant=tenant,
                store=store,
                report_run=locked_report_run,
                content=content,
                generated_at=generated_at,
            )

            locked_report_run.status = REPORT_RUN_STATUS_COMPLETED
            locked_report_run.error_message = ""
            locked_report_run.save(update_fields=["status", "error_message", "updated_at"])

        daily_report.refresh_from_db()
        return daily_report

    @staticmethod
    def _validate_coordinator_service(service_name: str) -> None:
        if service_name != AI_SERVICE_COORDINATOR:
            raise ReportRunPermissionError(
                "Only coordinator-agent may complete report runs."
            )

    @staticmethod
    def _validate_scope(
        *,
        report_run: ReportRun,
        tenant: Tenant,
        store: Store,
    ) -> None:
        if store.tenant_id != tenant.id:
            raise ReportRunScopeError("Store does not belong to the trusted tenant context.")
        if report_run.tenant_id != tenant.id or report_run.store_id != store.id:
            raise ReportRunScopeError(
                "Report run does not belong to the trusted tenant/store context."
            )

    @staticmethod
    def _validate_completable_status(report_run: ReportRun) -> None:
        if report_run.status == REPORT_RUN_STATUS_COMPLETED:
            raise ReportRunTransitionError(
                "Report run is already completed and cannot be completed again."
            )
        if report_run.status == REPORT_RUN_STATUS_FAILED:
            raise ReportRunTransitionError(
                "Failed report runs cannot be completed."
            )
        if report_run.status != REPORT_RUN_STATUS_RUNNING:
            raise ReportRunTransitionError(
                f"Report run cannot be completed from status {report_run.status!r}; "
                f"expected {REPORT_RUN_STATUS_RUNNING!r}."
            )

    @classmethod
    def _validate_and_normalize_report_payload(
        cls,
        report_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(report_payload, dict):
            raise ReportRunPayloadValidationError("report must be a JSON object.")

        generated_at_raw = report_payload.get("generated_at")
        if not generated_at_raw:
            raise ReportRunPayloadValidationError("report.generated_at is required.")

        generated_at = parse_datetime(str(generated_at_raw))
        if generated_at is None:
            raise ReportRunPayloadValidationError(
                "report.generated_at must be a valid ISO 8601 datetime."
            )

        period = report_payload.get("period")
        if period is not None and not isinstance(period, dict):
            raise ReportRunPayloadValidationError("report.period must be a JSON object.")

        return {"generated_at": generated_at}

    @staticmethod
    def _validate_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        if metadata is None:
            return {}
        if not isinstance(metadata, dict):
            raise ReportRunPayloadValidationError("metadata must be a JSON object.")
        return metadata

    @classmethod
    def _validate_agent_output_ids(
        cls,
        *,
        tenant: Tenant,
        store: Store,
        report_run: ReportRun,
        agent_output_ids: list,
    ) -> None:
        if not agent_output_ids:
            return

        unique_ids = list(dict.fromkeys(agent_output_ids))
        outputs = AgentOutput.objects.filter(
            pk__in=unique_ids,
            tenant=tenant,
            store=store,
        )
        if outputs.count() != len(unique_ids):
            raise ReportRunReferenceError(
                "One or more agent_output_ids are invalid for this tenant/store."
            )

        for agent_output in outputs:
            if (
                agent_output.report_run_id is not None
                and agent_output.report_run_id != report_run.id
            ):
                raise ReportRunReferenceError(
                    "One or more agent_output_ids do not belong to this report run."
                )

    @classmethod
    def _validate_action_ids(
        cls,
        *,
        tenant: Tenant,
        store: Store,
        report_run: ReportRun,
        action_ids: list,
    ) -> None:
        if not action_ids:
            return

        unique_ids = list(dict.fromkeys(action_ids))
        actions = Action.objects.filter(
            pk__in=unique_ids,
            tenant=tenant,
            store=store,
        )
        if actions.count() != len(unique_ids):
            raise ReportRunReferenceError(
                "One or more action_ids are invalid for this tenant/store."
            )

        for action in actions:
            if action.report_run_id is not None and action.report_run_id != report_run.id:
                raise ReportRunReferenceError(
                    "One or more action_ids do not belong to this report run."
                )
