"""Daily report workflow scaffold — star topology only (Step 10.1).

The coordinator-agent is the sole orchestrator. Specialist runs are initiated
only from coordinator workflow nodes via ``SpecialistAgentClient`` — never
peer-to-peer between specialist agents.

Full LangGraph node behavior, timeouts, persistence, merge, and submit are
deferred to later Phase 10 steps.
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
