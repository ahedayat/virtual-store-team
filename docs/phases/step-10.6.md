# Step 10.6 — LangGraph Workflow & Parallel Specialist Execution

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Replace the sequential coordinator workflow runner with a compiled LangGraph graph that fans out sales, content, and support specialist nodes in parallel after context fetch, while preserving all behavior from Steps 10.1–10.5.

---

## Scope

### In scope

- `langgraph` dependency in coordinator-agent requirements
- Compiled daily-report LangGraph in `agents/coordinator/graph.py`
- Graph nodes: `fetch_context`, `run_sales`, `run_content`, `run_support`, `merge`, `submit`
- Parallel specialist fan-out/fan-in after `fetch_context`
- `run_daily_report_workflow()` delegates to the graph-backed implementation
- Reuse of existing node functions from `nodes.py` (timeouts, persistence, merge, submit)
- Deterministic tests for graph shape, execution, parallelism, timeouts, persistence, partial failure
- Preservation of Steps 10.1–10.5 behavior

### Non-goals

| Area | Deferred work |
|------|----------------|
| **Step 10.7** | DB-backed final E2E verification and Phase 10 closure |
| **Phase 11** | Frontend/dashboard UI |
| **Phase 12** | Prestia demo polish |
| — | Real LLM providers or API keys |
| — | Real Instagram publish/send or external side effects |
| — | Direct database access from agents |
| — | Auto-approval or action execution |

**Step 10.7 DB-backed final E2E closure was not implemented in this step.**

---

## Implementation summary

### LangGraph module (`agents/coordinator/graph.py`)

- `DailyReportGraphState` — TypedDict mirroring `DailyReportWorkflowState` with `operator.add` reducers on `warnings` and `agent_outputs_ref`
- `build_daily_report_graph()` — compiles the StateGraph with injectable `WorkflowNodeDependencies`
- `invoke_daily_report_graph()` — converts workflow state, invokes graph, converts result back
- Node wrappers clone workflow state before calling existing `nodes.py` handlers so in-place mutation produces correct LangGraph partial updates

### Runner (`agents/coordinator/runner.py`)

- `run_daily_report_workflow()` now calls `invoke_daily_report_graph()` instead of sequential node calls
- Public signature unchanged; Step 10.5 endpoint and Celery handoff continue to use the same entrypoint

### Dependency (`agents/coordinator/requirements.txt`)

- Added `langgraph==0.2.76` (minimal pinned version compatible with Python 3.12)

---

## LangGraph design

```
START
  │
  ▼
fetch_context
  │
  ├─ failed ──────────────────────────────► END
  │
  └─ ok ──► ┌─ run_sales ────┐
            ├─ run_content ──┼──► merge ──► submit ──► END
            └─ run_support ──┘
                  (parallel superstep)
```

- **Star topology preserved:** coordinator graph nodes call specialists only through `SpecialistAgentClient`; no specialist-to-specialist edges
- **Critical path short-circuit:** `fetch_context` failure routes directly to `END` (no specialist or merge/submit execution)
- **Merge failure short-circuit:** `merge` failure skips `submit`

---

## Graph nodes and responsibilities

| Node | Responsibility | Critical? |
|------|----------------|-----------|
| `fetch_context` | Django context bundle via `DjangoClient.get_context_bundle` | Yes — timeout fails workflow |
| `run_sales` | Sales specialist `POST /run` + AgentOutput persistence | No — timeout → warning |
| `run_content` | Content specialist `POST /run` + AgentOutput persistence | No — timeout → warning |
| `run_support` | Support specialist `POST /run` + AgentOutput persistence | No — timeout → warning |
| `merge` | `build_merged_daily_report()` with partial-section support | Yes — timeout fails workflow |
| `submit` | `DjangoClient.complete_report_run()` | Yes — timeout fails workflow |

All nodes reuse existing implementations from `agents/coordinator/nodes.py`.

---

## Parallel / fan-out / fan-in behavior

After successful `fetch_context`, LangGraph `add_conditional_edges` returns `[run_sales, run_content, run_support]`, executing all three in the same superstep. Each specialist node writes to a distinct state key (`sales_output`, `content_output`, `support_output`). List fields (`warnings`, `agent_outputs_ref`) use `Annotated[..., operator.add]` reducers to concatenate parallel updates.

`merge` has incoming edges from all three specialist nodes; LangGraph waits for the slowest specialist before proceeding (required fan-in). Tests verify:

- Fast specialists complete before a slow specialist finishes
- Total specialist phase duration is bounded by the slowest node (~0.15s × 3 parallel ≈ 0.15s), not the sum (~0.45s sequential)

**Note:** Warning order among parallel specialist nodes may differ from sequential execution; warning *codes* and partial-report semantics are preserved.

---

## How Step 10.1 star topology is preserved

- Graph contains only coordinator nodes; specialist agents are invoked via HTTP from coordinator node handlers
- No new inter-agent HTTP paths; `SPECIALIST_PEER_CALL_PATHS` remains empty
- Step 10.1 star topology tests pass unchanged

---

## How Step 10.2 timeout behavior is preserved

- Each graph node wraps the same `nodes.py` handler that calls `run_with_node_timeout()`
- Per-node timeout env configuration unchanged (`COORDINATOR_*_TIMEOUT_SECONDS`)
- Critical node timeouts (`fetch_context`, `merge`, `submit`) fail the workflow
- Specialist timeouts produce `specialist_node_timeout` + `agent_output_not_persisted` warnings
- Graph execution timeout tests pass

---

## How Step 10.3 AgentOutput persistence is preserved

- Specialist graph nodes call `_persist_specialist_output()` inside existing `_run_specialist_node()`
- Returned `agent_output_id` values accumulate via `agent_outputs_ref` reducer
- Final report includes `agent_outputs_ref` through unchanged merge/submit path
- Graph persistence tests pass (3 AgentOutput records on success path)

---

## How Step 10.5 endpoint/Celery wiring is preserved

- `POST /workflows/daily-report` still calls `run_daily_report_workflow()` via `execute_daily_report_workflow()`
- Request/response contract unchanged
- Celery `reports.generate_daily` coordinator client and completion verification unchanged
- Step 10.5 endpoint tests (15) and backend Celery tests (22) pass

---

## Partial failure behavior

- Specialist timeout: workflow continues; `warnings[]` includes structured codes; `merged_report.partial=true` with `missing_sections`
- Successful specialist outputs still merged and submitted
- Critical failures (`fetch_context`, `merge`, `submit` timeouts): `status=failed`, sanitized `error_message`
- No auto-approve or action execution introduced

---

## Files changed

| File | Change |
|------|--------|
| `agents/coordinator/graph.py` | **Created** — LangGraph StateGraph, state adapters, parallel routing |
| `agents/coordinator/runner.py` | **Updated** — delegates to `invoke_daily_report_graph()` |
| `agents/coordinator/workflow.py` | **Updated** — Step 10.6 note |
| `agents/coordinator/requirements.txt` | **Updated** — `langgraph==0.2.76` |
| `agents/coordinator/tests/test_langgraph_workflow.py` | **Created** — graph compilation, parallelism, timeout, persistence tests |
| `docs/phases/step-10.6.md` | **Created** — this document |

---

## Tests added

| Module | Coverage |
|--------|----------|
| `test_langgraph_workflow.py` | Graph compiles; contains all 6 logical nodes; mock execution succeeds; parallel completion ordering; timeout preservation; AgentOutput persistence; partial failure warnings |

---

## Verification commands run

```bash
python -m unittest agents.coordinator.tests.test_langgraph_workflow -v
python -m unittest \
  agents.coordinator.tests.test_star_topology \
  agents.coordinator.tests.test_node_timeouts \
  agents.coordinator.tests.test_agent_output_persistence \
  agents.coordinator.tests.test_full_graph_integration \
  agents.coordinator.tests.test_daily_report_endpoint \
  agents.coordinator.tests.test_langgraph_workflow -v
cd backend && python manage.py test \
  operations.tests.test_generate_daily_task \
  operations.tests.test_coordinator_integration -v 2
```

---

## Results

| Suite | Result |
|-------|--------|
| Step 10.6 LangGraph tests (11 tests) | **Passed** |
| Step 10.1 star topology | **Passed** (preserved) |
| Step 10.2 node timeouts | **Passed** (preserved) |
| Step 10.3 AgentOutput persistence | **Passed** (preserved) |
| Step 10.4 full graph integration | **Passed** (preserved) |
| Step 10.5 endpoint tests (15 tests) | **Passed** (preserved) |
| Backend Celery/coordinator tests (22 tests) | **Passed** (preserved) |
| **Total coordinator Phase 10 tests** | **86 passed** |

---

## Known limitations

- Warning ordering among parallel specialist nodes is not strictly sequential; codes and partial-report semantics are preserved
- Graph compiles per invocation with injected dependencies (no shared compiled singleton); acceptable for MVP coordinator throughput
- Step 10.4 integration harness exercises `run_daily_report_workflow()` which now uses LangGraph internally — no harness changes required
- DB-backed Celery → coordinator → Django E2E with real Postgres rows remains Step 10.7
- Specialist HTTP errors (non-timeout 4xx/5xx) are not converted to partial-report warnings (unchanged from Step 10.4)

---

## Explicit deferrals

- **Step 10.7 — DB-backed final E2E verification and Phase 10 closure — was not implemented in this step.**
- **Phase 11 frontend/dashboard work was not implemented in this step.**
- **Phase 12 Prestia demo polish was not implemented in this step.**
