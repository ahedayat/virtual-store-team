from __future__ import annotations

from typing import Any

from django.db import transaction

from operations.constants import (
    ACTION_EVENT_TYPE_CREATED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_TYPE_SUPPORT_REPLY_DRAFT,
    ALLOWED_AGENT_NAMES,
    DEFAULT_REQUIRES_APPROVAL_BY_ACTION_TYPE,
    MAX_ACTION_PRIORITY,
    MIN_ACTION_PRIORITY,
    SUPPORTED_ACTION_TYPES,
)
from operations.exceptions import ActionPayloadValidationError, ActionScopeError
from operations.models import Action, ActionEvent, ActionEventActorType, AgentOutput
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
