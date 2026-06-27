"""Coordinator daily report workflow state (Step 10.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.shared.schemas.base import AgentWarning


@dataclass
class DailyReportWorkflowState:
    """Mutable state passed through coordinator workflow nodes."""

    report_run_id: str
    tenant_id: str
    store_id: str
    service_token: str | None = None
    request_id: str | None = None
    context: dict[str, Any] | None = None
    sales_output: dict[str, Any] | None = None
    content_output: dict[str, Any] | None = None
    support_output: dict[str, Any] | None = None
    agent_outputs_ref: list[str] = field(default_factory=list)
    merged_report: dict[str, Any] | None = None
    submit_result: dict[str, Any] | None = None
    warnings: list[AgentWarning] = field(default_factory=list)
    failed: bool = False
    error_message: str | None = None
    status: str = "running"
