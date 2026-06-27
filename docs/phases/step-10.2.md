# Step 10.2 — Coordinator Node Timeouts

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Add deterministic per-node timeout protection to the coordinator-agent daily report workflow. Every workflow node (`fetch_context`, `run_sales`, `run_content`, `run_support`, `merge`, `submit`) must enforce a configurable timeout boundary without breaking the Step 10.1 star topology.

---

## Scope

### In scope

- Typed coordinator timeout configuration module with environment variables and safe defaults
- Reusable synchronous timeout helper with structured errors and safe logging
- Executable workflow node handlers with timeout boundaries
- Sequential workflow runner (`run_daily_report_workflow`) for testing and future LangGraph wiring
- Specialist timeout → structured `AgentWarning`, partial merge when context is available
- Critical node timeout (`fetch_context`, `merge`, `submit`) → safe workflow failure with sanitized errors
- Minimal `DjangoClient` extensions for context fetch and report completion HTTP calls
- Deterministic unit tests (no live services or LLM keys)
- `.env.example` documentation for new timeout variables

### Non-goals (explicit)

| Area | Deferred work |
|------|----------------|
| **Step 10.3** | Intermediate `AgentOutput` persistence via Django client |
| **Step 10.4** | Full graph integration test |
| — | LangGraph dependency or compiled graph |
| — | Wiring `POST /workflows/daily-report` to run the full workflow (stub preserved) |
| — | Real external side effects, LLM calls, or auto-approval/execution |
| — | Specialist agent behavior changes |
| — | Agent mesh or peer-to-peer specialist HTTP calls |

**Step 10.3 intermediate AgentOutput persistence was not implemented in this step.**

---

## Timeout configuration

Environment variables (invalid, missing, zero, or negative values fall back to defaults):

| Variable | Default (seconds) | Node |
|----------|-------------------|------|
| `COORDINATOR_FETCH_CONTEXT_TIMEOUT_SECONDS` | 30 | `fetch_context` |
| `COORDINATOR_SALES_TIMEOUT_SECONDS` | 60 | `run_sales` |
| `COORDINATOR_CONTENT_TIMEOUT_SECONDS` | 60 | `run_content` |
| `COORDINATOR_SUPPORT_TIMEOUT_SECONDS` | 60 | `run_support` |
| `COORDINATOR_MERGE_TIMEOUT_SECONDS` | 30 | `merge` |
| `COORDINATOR_SUBMIT_TIMEOUT_SECONDS` | 30 | `submit` |

Load via `load_coordinator_node_timeouts()` → `CoordinatorNodeTimeouts.timeout_for_node(node_name)`.

HTTP clients receive the matching per-node timeout when constructed:

- `DjangoClient(timeout_seconds=...)` for `fetch_context` and `submit`
- `SpecialistAgentClient(timeout_seconds=...)` for specialist run nodes

---

## Implementation summary

### Timeout helper (`agents/coordinator/timeout.py`)

- `run_with_node_timeout()` — wraps synchronous node work using `ThreadPoolExecutor` + `future.result(timeout=...)`
- `CoordinatorNodeTimeoutError` — structured internal timeout error (node name, timeout seconds, duration ms)
- `build_specialist_timeout_warning()` — `AgentWarning(code="specialist_node_timeout", ...)`
- `log_node_timeout()` — logs only `report_run_id`, `node_name`, `timeout_seconds`, `duration_ms`, `service_name`
- Sanitized error messages — no JWTs, prompts, payloads, or PII

### Node behavior (`agents/coordinator/nodes.py`)

| Node | Timeout failure behavior |
|------|--------------------------|
| `fetch_context` | Critical — workflow `failed`, sanitized error, no downstream nodes |
| `run_sales` / `run_content` / `run_support` | Warning added, section omitted, workflow continues |
| `merge` | Critical — workflow `failed` if merge itself times out |
| `submit` | Critical — workflow `failed`, sanitized error |

Merge builds a partial report when specialist sections are missing; timed-out sections appear in `missing_sections` — no fabricated agent output.

### Star topology preserved

- Specialist calls still go only through `SpecialistAgentClient` from coordinator nodes
- `SPECIALIST_PEER_CALL_PATHS` remains empty
- No specialist-to-specialist HTTP wiring introduced

### Stub endpoint unchanged

`POST /workflows/daily-report` still returns the Phase 6.4 deterministic stub response. The timeout-enabled workflow is available via `run_daily_report_workflow()` for tests and future orchestration wiring.

---

## Files changed

| File | Change |
|------|--------|
| `agents/coordinator/config.py` | Created — timeout env loading and defaults |
| `agents/coordinator/timeout.py` | Created — reusable timeout helper and warnings |
| `agents/coordinator/state.py` | Created — `DailyReportWorkflowState` |
| `agents/coordinator/nodes.py` | Created — timed workflow node handlers |
| `agents/coordinator/runner.py` | Created — sequential workflow runner |
| `agents/coordinator/workflow.py` | Updated — docstring references Step 10.2 |
| `agents/coordinator/tests/test_node_timeouts.py` | Created — 18 timeout/topology tests |
| `agents/shared/django_client/client.py` | Updated — `get_context_bundle()`, `complete_report_run()` |
| `.env.example` | Updated — per-node coordinator timeout variables |
| `docs/phases/step-10.2.md` | Created — this document |

**Unchanged:** Coordinator FastAPI stub (`agents/coordinator/app/main.py`), specialist agent services, Step 10.3 persistence.

---

## Tests added

`agents/coordinator/tests/test_node_timeouts.py` (18 tests):

- Timeout config defaults and invalid env fallback
- Node completes before timeout / exceeds timeout with structured error
- Specialist timeout → warning + partial merge
- Full partial workflow continues to submit when one specialist times out
- Critical `fetch_context` and `submit` timeouts fail safely
- HTTP clients receive configured timeout values
- Star topology preserved (no peer paths, no specialist business imports)

---

## Verification commands run

```bash
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_node_timeouts -v
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_star_topology -v
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_daily_report_stub -v
PYTHONPATH=. python -m unittest discover agents/coordinator/tests -v
```

**Results:**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_node_timeouts` | 18 | Passed |
| `test_star_topology` | 20 | Passed |
| `test_daily_report_stub` | 14 | Passed |
| `discover agents/coordinator/tests` | 52 | Passed |

---

## Known limitations

- Workflow runs sequentially (not LangGraph); parallel specialist execution is deferred
- `POST /workflows/daily-report` does not invoke the timed workflow yet
- Merge/submit payloads are minimal MVP shapes — full report schema alignment is deferred
- Node timeout uses thread-based enforcement; extremely slow HTTP clients may need httpx-level timeouts aligned with node timeouts (both are set from the same config)
- Step 10.3 intermediate `AgentOutput` persistence is not implemented

---

## Completion decision

**Phase 10.2 is complete.** Every coordinator workflow node has deterministic timeout protection, configurable defaults, specialist partial-report behavior, and safe critical failure handling while preserving Step 10.1 star topology.

---

## Next steps

| Step | Focus |
|------|-------|
| **10.3** | Persist intermediate `AgentOutput` records via Django client |
| **10.4** | Full graph integration test with mock LLM across services |
| **10+** | LangGraph wiring, Celery stub → live orchestration |
