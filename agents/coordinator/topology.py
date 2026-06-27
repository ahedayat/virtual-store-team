"""Star-topology contract for coordinator-orchestrated specialist agent calls."""

from __future__ import annotations

import os
from enum import Enum
from typing import Final, Mapping

from agents.shared.django_client.client import join_url, normalize_base_url

SPECIALIST_RUN_PATH: Final[str] = "/run"
COORDINATOR_SERVICE_NAME: Final[str] = "coordinator-agent"


class SpecialistAgentName(str, Enum):
    """Specialist agents the coordinator may call directly."""

    SALES = "sales"
    CONTENT = "content"
    SUPPORT = "support"


class UnknownSpecialistAgentError(ValueError):
    """Raised when a specialist agent name is outside the star topology."""


SPECIALIST_AGENT_URL_ENV_VARS: Final[Mapping[SpecialistAgentName, str]] = {
    SpecialistAgentName.SALES: "SALES_AGENT_URL",
    SpecialistAgentName.CONTENT: "CONTENT_AGENT_URL",
    SpecialistAgentName.SUPPORT: "SUPPORT_AGENT_URL",
}

# Compose-friendly defaults when an env var is unset (not tenant-specific).
SPECIALIST_AGENT_DEFAULT_BASE_URLS: Final[Mapping[SpecialistAgentName, str]] = {
    SpecialistAgentName.SALES: "http://sales-agent:8101",
    SpecialistAgentName.CONTENT: "http://content-agent:8102",
    SpecialistAgentName.SUPPORT: "http://support-agent:8103",
}

# Star topology: coordinator is the hub; specialists never call each other.
# This set must remain empty — peer edges are disallowed by design.
SPECIALIST_PEER_CALL_PATHS: Final[frozenset[tuple[SpecialistAgentName, SpecialistAgentName]]] = (
    frozenset()
)


def get_allowed_specialist_agents() -> frozenset[SpecialistAgentName]:
    """Return the specialist agents the coordinator may call."""
    return frozenset(SpecialistAgentName)


def parse_specialist_agent_name(value: str) -> SpecialistAgentName:
    """Parse and validate a specialist agent name."""
    normalized = value.strip().lower()
    try:
        return SpecialistAgentName(normalized)
    except ValueError as exc:
        allowed = ", ".join(agent.value for agent in SpecialistAgentName)
        raise UnknownSpecialistAgentError(
            f"Unknown specialist agent {value!r}. Allowed: {allowed}."
        ) from exc


def resolve_specialist_base_url(
    agent_name: SpecialistAgentName | str,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Resolve a specialist service base URL from settings/environment."""
    parsed = (
        agent_name
        if isinstance(agent_name, SpecialistAgentName)
        else parse_specialist_agent_name(agent_name)
    )
    env_vars = env if env is not None else os.environ
    env_var = SPECIALIST_AGENT_URL_ENV_VARS[parsed]
    raw_value = env_vars.get(env_var)
    if raw_value is not None and str(raw_value).strip():
        return normalize_base_url(str(raw_value).strip())
    return normalize_base_url(SPECIALIST_AGENT_DEFAULT_BASE_URLS[parsed])


def build_specialist_run_url(
    agent_name: SpecialistAgentName | str,
    *,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Build the specialist agent ``POST /run`` URL for the given agent."""
    parsed = (
        agent_name
        if isinstance(agent_name, SpecialistAgentName)
        else parse_specialist_agent_name(agent_name)
    )
    resolved_base_url = base_url or resolve_specialist_base_url(parsed, env=env)
    return join_url(resolved_base_url, SPECIALIST_RUN_PATH)


def assert_star_topology() -> None:
    """Validate the coordinator star-topology contract (for tests and startup checks)."""
    allowed = get_allowed_specialist_agents()
    if allowed != frozenset(SpecialistAgentName):
        raise AssertionError("Allowed specialist agents must be sales, content, and support.")

    expected_names = {"sales", "content", "support"}
    if {agent.value for agent in allowed} != expected_names:
        raise AssertionError(
            f"Specialist agent names must be exactly {sorted(expected_names)}."
        )

    for agent in allowed:
        if agent not in SPECIALIST_AGENT_URL_ENV_VARS:
            raise AssertionError(f"Missing URL env mapping for specialist agent {agent.value}.")
        if agent not in SPECIALIST_AGENT_DEFAULT_BASE_URLS:
            raise AssertionError(
                f"Missing default base URL for specialist agent {agent.value}."
            )

    if SPECIALIST_PEER_CALL_PATHS:
        raise AssertionError(
            "Specialist peer-to-peer call paths must not be defined in star topology."
        )

    if COORDINATOR_SERVICE_NAME != "coordinator-agent":
        raise AssertionError("Coordinator service name must be coordinator-agent.")
