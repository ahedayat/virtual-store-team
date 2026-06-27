"""Reusable timeout helpers for coordinator workflow nodes (Step 10.2)."""

from __future__ import annotations

import concurrent.futures
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from agents.shared.schemas.base import AgentWarning

logger = logging.getLogger(__name__)

T = TypeVar("T")

SPECIALIST_NODE_TIMEOUT_WARNING_CODE = "specialist_node_timeout"
CRITICAL_NODE_TIMEOUT_ERROR_CODE = "critical_node_timeout"


@dataclass(frozen=True)
class NodeTimeoutResult:
    """Structured timeout outcome for coordinator node execution."""

    node_name: str
    timeout_seconds: float
    duration_ms: float
    timed_out: bool
    service_name: str | None = None


class CoordinatorNodeTimeoutError(Exception):
    """Raised when a coordinator workflow node exceeds its timeout boundary."""

    def __init__(
        self,
        *,
        node_name: str,
        timeout_seconds: float,
        duration_ms: float | None = None,
        service_name: str | None = None,
    ) -> None:
        self.node_name = node_name
        self.timeout_seconds = timeout_seconds
        self.duration_ms = duration_ms
        self.service_name = service_name
        super().__init__(
            sanitize_timeout_error_message(
                node_name=node_name,
                critical=True,
            )
        )


def sanitize_timeout_error_message(
    *,
    node_name: str,
    critical: bool = False,
) -> str:
    """Return a safe, non-sensitive timeout message for logs and API responses."""
    if critical:
        return (
            f"Coordinator workflow node '{node_name}' timed out; "
            "daily report cannot continue safely."
        )
    return f"Coordinator workflow node '{node_name}' timed out."


def build_specialist_timeout_warning(
    node_name: str,
    *,
    timeout_seconds: float,
) -> AgentWarning:
    """Structured warning when a specialist run node times out."""
    specialist = node_name.removeprefix("run_")
    return AgentWarning(
        code=SPECIALIST_NODE_TIMEOUT_WARNING_CODE,
        message=(
            f"Specialist agent '{specialist}' did not respond within "
            f"{int(timeout_seconds)} seconds; section omitted from report."
        ),
    )


def log_node_timeout(
    *,
    report_run_id: str | None,
    node_name: str,
    timeout_seconds: float,
    duration_ms: float | None,
    service_name: str | None = None,
) -> None:
    """Log a timeout event with safe metadata only."""
    logger.warning(
        "Coordinator workflow node timed out",
        extra={
            "report_run_id": report_run_id,
            "node_name": node_name,
            "timeout_seconds": timeout_seconds,
            "duration_ms": duration_ms,
            "service_name": service_name,
        },
    )


def run_with_node_timeout(
    node_name: str,
    timeout_seconds: float,
    operation: Callable[[], T],
    *,
    report_run_id: str | None = None,
    service_name: str | None = None,
) -> T:
    """Execute a synchronous node operation with a deterministic timeout boundary."""
    started = time.monotonic()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(operation)
    try:
        result = future.result(timeout=timeout_seconds)
        return result
    except concurrent.futures.TimeoutError as exc:
        duration_ms = (time.monotonic() - started) * 1000.0
        log_node_timeout(
            report_run_id=report_run_id,
            node_name=node_name,
            timeout_seconds=timeout_seconds,
            duration_ms=duration_ms,
            service_name=service_name,
        )
        raise CoordinatorNodeTimeoutError(
            node_name=node_name,
            timeout_seconds=timeout_seconds,
            duration_ms=duration_ms,
            service_name=service_name,
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
