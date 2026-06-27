"""Daily report workflow scaffold — star topology (Step 10.1) and node timeouts (10.2).

The coordinator-agent is the sole orchestrator. Specialist runs are initiated
only from coordinator workflow nodes via ``SpecialistAgentClient`` — never
peer-to-peer between specialist agents.

Step 10.2 adds executable node handlers with per-node timeout boundaries in
``agents.coordinator.nodes`` and ``agents.coordinator.runner``. Step 10.3 adds
intermediate AgentOutput persistence via the shared Django client. LangGraph graph
wiring and full integration tests (10.4) remain deferred.
"""

from __future__ import annotations

from typing import Final

WORKFLOW_NODE_FETCH_CONTEXT: Final[str] = "fetch_context"
WORKFLOW_NODE_RUN_SALES: Final[str] = "run_sales"
WORKFLOW_NODE_RUN_CONTENT: Final[str] = "run_content"
WORKFLOW_NODE_RUN_SUPPORT: Final[str] = "run_support"
WORKFLOW_NODE_MERGE: Final[str] = "merge"
WORKFLOW_NODE_SUBMIT: Final[str] = "submit"

DAILY_REPORT_WORKFLOW_NODES: Final[tuple[str, ...]] = (
    WORKFLOW_NODE_FETCH_CONTEXT,
    WORKFLOW_NODE_RUN_SALES,
    WORKFLOW_NODE_RUN_CONTENT,
    WORKFLOW_NODE_RUN_SUPPORT,
    WORKFLOW_NODE_MERGE,
    WORKFLOW_NODE_SUBMIT,
)

# Specialist run nodes must delegate through SpecialistAgentClient only.
SPECIALIST_RUN_NODES: Final[frozenset[str]] = frozenset(
    {
        WORKFLOW_NODE_RUN_SALES,
        WORKFLOW_NODE_RUN_CONTENT,
        WORKFLOW_NODE_RUN_SUPPORT,
    }
)
