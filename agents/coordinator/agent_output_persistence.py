"""Coordinator-side AgentOutput persistence via Django internal API (Step 10.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from agents.coordinator.workflow import (
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
)
from agents.shared.django_client import DjangoClient, DjangoClientError
from agents.shared.schemas.base import AgentWarning

SPECIALIST_OUTPUT_TYPES: Final[dict[str, str]] = {
    WORKFLOW_NODE_RUN_SALES: "sales_analysis",
    WORKFLOW_NODE_RUN_CONTENT: "content_suggestions",
    WORKFLOW_NODE_RUN_SUPPORT: "support_insights",
}

SPECIALIST_SOURCE_AGENT_NAMES: Final[dict[str, str]] = {
    WORKFLOW_NODE_RUN_SALES: "sales-agent",
    WORKFLOW_NODE_RUN_CONTENT: "content-agent",
    WORKFLOW_NODE_RUN_SUPPORT: "support-agent",
}

_UNTRUSTED_SCOPE_FIELDS = frozenset({"tenant_id", "store_id"})


@dataclass(frozen=True)
class AgentOutputPersistenceResult:
    """Structured result from a coordinator AgentOutput persistence attempt."""

    agent_output_id: str | None
    persisted: bool
    warning: AgentWarning | None = None


def sanitize_specialist_output_payload(output: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of specialist output with untrusted scope fields removed."""
    sanitized = {key: value for key, value in output.items() if key not in _UNTRUSTED_SCOPE_FIELDS}

    metadata = sanitized.get("metadata")
    if isinstance(metadata, dict):
        sanitized["metadata"] = {
            key: value for key, value in metadata.items() if key not in _UNTRUSTED_SCOPE_FIELDS
        }

    return sanitized


def build_agent_output_request(
    *,
    report_run_id: str,
    node_name: str,
    specialist_output: dict[str, Any],
) -> dict[str, Any]:
    """Build a Django ``POST /internal/ai/agent-outputs/`` request body."""
    output_type = SPECIALIST_OUTPUT_TYPES[node_name]
    source_agent_name = SPECIALIST_SOURCE_AGENT_NAMES[node_name]

    return {
        "output_type": output_type,
        "payload": sanitize_specialist_output_payload(specialist_output),
        "metadata": {
            "source_agent_name": source_agent_name,
            "coordinator_node": node_name,
        },
        "report_run_id": report_run_id,
    }


def build_agent_output_not_persisted_warning(*, node_name: str) -> AgentWarning:
    """Warning when no AgentOutput is persisted because the specialist node did not succeed."""
    return AgentWarning(
        code="agent_output_not_persisted",
        message=(
            f"No agent output was persisted for {node_name} because the specialist "
            "node did not complete successfully."
        ),
    )


def build_agent_output_persistence_failed_warning(*, node_name: str) -> AgentWarning:
    """Safe warning when Django AgentOutput persistence fails."""
    return AgentWarning(
        code="agent_output_persistence_failed",
        message=(
            f"Could not persist {node_name} output to Django; "
            "workflow continues with the in-memory specialist result."
        ),
    )


def persist_specialist_agent_output(
    *,
    django_client: DjangoClient,
    report_run_id: str,
    node_name: str,
    specialist_output: dict[str, Any],
) -> AgentOutputPersistenceResult:
    """Persist a successful specialist output through Django internal API."""
    request_body = build_agent_output_request(
        report_run_id=report_run_id,
        node_name=node_name,
        specialist_output=specialist_output,
    )

    try:
        response = django_client.create_agent_output(request_body)
    except DjangoClientError:
        return AgentOutputPersistenceResult(
            agent_output_id=None,
            persisted=False,
            warning=build_agent_output_persistence_failed_warning(node_name=node_name),
        )

    agent_output_id = response.get("id")
    if not isinstance(agent_output_id, str) or not agent_output_id.strip():
        return AgentOutputPersistenceResult(
            agent_output_id=None,
            persisted=False,
            warning=build_agent_output_persistence_failed_warning(node_name=node_name),
        )

    return AgentOutputPersistenceResult(
        agent_output_id=agent_output_id.strip(),
        persisted=True,
    )
