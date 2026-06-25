from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole
from operations.constants import (
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_EVENT_TYPE_QUEUED,
    ACTION_EVENT_TYPE_REJECTED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_STATUS_REJECTED,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
    ALLOWED_AGENT_NAMES,
    DEFAULT_REQUIRES_APPROVAL_BY_ACTION_TYPE,
    MAX_ACTION_PRIORITY,
    MIN_ACTION_PRIORITY,
    SUPPORTED_ACTION_TYPES,
)
from operations.exceptions import (
    ActionPayloadValidationError,
    ActionScopeError,
    ActionTransitionError,
    AgentOutputPayloadValidationError,
    AgentOutputScopeError,
)
from operations.models import Action, ActionEvent, ActionEventActorType, AgentOutput, ReportRun
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
