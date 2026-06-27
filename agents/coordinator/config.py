"""Coordinator workflow configuration (Step 10.2 — per-node timeouts)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from agents.coordinator.workflow import (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_SUBMIT,
)

ENV_FETCH_CONTEXT_TIMEOUT: Final[str] = "COORDINATOR_FETCH_CONTEXT_TIMEOUT_SECONDS"
ENV_SALES_TIMEOUT: Final[str] = "COORDINATOR_SALES_TIMEOUT_SECONDS"
ENV_CONTENT_TIMEOUT: Final[str] = "COORDINATOR_CONTENT_TIMEOUT_SECONDS"
ENV_SUPPORT_TIMEOUT: Final[str] = "COORDINATOR_SUPPORT_TIMEOUT_SECONDS"
ENV_MERGE_TIMEOUT: Final[str] = "COORDINATOR_MERGE_TIMEOUT_SECONDS"
ENV_SUBMIT_TIMEOUT: Final[str] = "COORDINATOR_SUBMIT_TIMEOUT_SECONDS"

DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_SALES_TIMEOUT_SECONDS: Final[float] = 60.0
DEFAULT_CONTENT_TIMEOUT_SECONDS: Final[float] = 60.0
DEFAULT_SUPPORT_TIMEOUT_SECONDS: Final[float] = 60.0
DEFAULT_MERGE_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_SUBMIT_TIMEOUT_SECONDS: Final[float] = 30.0


def _coerce_positive_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
    else:
        return None

    if parsed <= 0:
        return None
    return parsed


def _read_timeout(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None:
        return default
    parsed = _coerce_positive_float(raw)
    return default if parsed is None else parsed


@dataclass(frozen=True)
class CoordinatorNodeTimeouts:
    fetch_context_seconds: float = DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS
    sales_seconds: float = DEFAULT_SALES_TIMEOUT_SECONDS
    content_seconds: float = DEFAULT_CONTENT_TIMEOUT_SECONDS
    support_seconds: float = DEFAULT_SUPPORT_TIMEOUT_SECONDS
    merge_seconds: float = DEFAULT_MERGE_TIMEOUT_SECONDS
    submit_seconds: float = DEFAULT_SUBMIT_TIMEOUT_SECONDS

    def timeout_for_node(self, node_name: str) -> float:
        mapping = {
            WORKFLOW_NODE_FETCH_CONTEXT: self.fetch_context_seconds,
            WORKFLOW_NODE_RUN_SALES: self.sales_seconds,
            WORKFLOW_NODE_RUN_CONTENT: self.content_seconds,
            WORKFLOW_NODE_RUN_SUPPORT: self.support_seconds,
            WORKFLOW_NODE_MERGE: self.merge_seconds,
            WORKFLOW_NODE_SUBMIT: self.submit_seconds,
        }
        try:
            return mapping[node_name]
        except KeyError as exc:
            raise ValueError(f"Unknown coordinator workflow node: {node_name}") from exc


def load_coordinator_node_timeouts(
    env: Mapping[str, str] | None = None,
) -> CoordinatorNodeTimeouts:
    """Load per-node timeout settings from environment with safe defaults."""
    source = os.environ if env is None else env
    return CoordinatorNodeTimeouts(
        fetch_context_seconds=_read_timeout(
            source,
            ENV_FETCH_CONTEXT_TIMEOUT,
            DEFAULT_FETCH_CONTEXT_TIMEOUT_SECONDS,
        ),
        sales_seconds=_read_timeout(
            source,
            ENV_SALES_TIMEOUT,
            DEFAULT_SALES_TIMEOUT_SECONDS,
        ),
        content_seconds=_read_timeout(
            source,
            ENV_CONTENT_TIMEOUT,
            DEFAULT_CONTENT_TIMEOUT_SECONDS,
        ),
        support_seconds=_read_timeout(
            source,
            ENV_SUPPORT_TIMEOUT,
            DEFAULT_SUPPORT_TIMEOUT_SECONDS,
        ),
        merge_seconds=_read_timeout(
            source,
            ENV_MERGE_TIMEOUT,
            DEFAULT_MERGE_TIMEOUT_SECONDS,
        ),
        submit_seconds=_read_timeout(
            source,
            ENV_SUBMIT_TIMEOUT,
            DEFAULT_SUBMIT_TIMEOUT_SECONDS,
        ),
    )
