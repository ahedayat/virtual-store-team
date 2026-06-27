# Step 10.4 — Full Graph Mock Integration

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Add deterministic integration coverage for the full daily-report coordinator workflow using mock LLM behavior across coordinator, sales-agent, content-agent, support-agent, and Django internal APIs — without real LLM API keys or external side effects.

---

## Scope

### In scope

- Full-graph integration tests exercising `run_daily_report_workflow()`
- In-process specialist FastAPI `/run` endpoints with `LLM_PROVIDER=mock`
- Faithful Django internal API test double (context, agent-outputs, report completion)
- Enhanced merge node producing the Phase 4 daily report payload shape
- Specialist-specific coordinator payloads compatible with each agent request schema
- Partial-failure coverage via support-agent timeout
- Star topology, action workflow, and AgentOutput persistence verification
- Preservation of Steps 10.1–10.3 behavior

### Non-goals

| Area | Deferred work |
|------|----------------|
| **Phase 11** | Frontend/dashboard UI |
| **Phase 12** | Prestia demo polish |
| — | LangGraph compiled graph wiring |
| — | Wiring `POST /workflows/daily-report` to the full workflow (stub endpoint unchanged) |
| — | Real LLM providers or API keys |
| — | Real Instagram publish/send or external side effects |
| — | Coordinator auto-approval or action execution |
| — | Docker-compose live multi-container smoke test |
| — | Celery → coordinator → Django DB end-to-end in this step |

**Phase 11 frontend work was not implemented in this step.**  
**Phase 12 Prestia demo polish was not implemented in this step.**

---

## Integration test strategy

The harness in `agents/coordinator/tests/integration_harness.py` uses:

1. **`run_daily_report_workflow()`** — real coordinator runner and node executors
2. **`httpx.MockTransport` router** — dispatches by host to:
   - Django mock (`RecordingDjangoState`) for internal AI endpoints
   - FastAPI `TestClient` bridges for sales/content/support `/run`
3. **`LLM_PROVIDER=mock`** — patched in integration tests; no external API keys
4. **Recording assertions** — HTTP call log, Django call log, specialist request bodies

This exercises real coordinator graph logic, real specialist request/response schemas, and real Django client code paths without live containers.

---

## Mock LLM / service setup

| Component | Mock approach |
|-----------|----------------|
| Sales / content / support | In-process FastAPI apps + `MockProvider` via `LLM_PROVIDER=mock` |
| Django context | `GET /internal/ai/context/{report_run_id}/` returns `INTEGRATION_CONTEXT_BUNDLE` |
| AgentOutput persistence | `POST /internal/ai/agent-outputs/` returns deterministic UUIDs |
| Report completion | `POST /internal/ai/report-runs/{id}/complete/` returns `status: completed` |
| Actions | Endpoint exists in mock but is **not called** by coordinator |

Specialist payloads from coordinator set `persist_actions=False`, `dry_run=True`, and `fetch_from_django=False` (sales/support) so no action persistence or external fetch occurs.

---

## Success-path verification

Integration tests prove:

- Coordinator fetches context from Django test double
- Coordinator calls sales, content, and support via `POST /run`
- Specialist responses are schema-compatible (`SalesAnalysisResult`, `ContentSuggestions`, `SupportRunResponse`)
- Three `AgentOutput` records are persisted; IDs captured in `agent_outputs_ref`
- Merge produces final report with:
  - `sales_summary`
  - `prioritized_actions`
  - `content_suggestions`
  - `support_insights`
  - `next_steps`
  - `agent_outputs_ref`
  - `generated_at`
- Final report submitted via `complete_report_run()`
- Workflow `status=completed`

---

## Partial-failure verification

`test_support_timeout_produces_partial_report_with_warnings` simulates support-agent timeout:

- Workflow does not crash; `status=completed`
- `support_output` is `None`; sales and content outputs remain merged
- `merged_report.partial` is `True`; `missing_sections` includes `support`
- `warnings[]` includes `specialist_node_timeout`
- Only two AgentOutput persistence calls (sales + content)
- Warnings contain no JWTs, Bearer tokens, or customer PII

---

## Action workflow verification

- Coordinator never calls `POST /internal/ai/actions/`
- Sales/support payloads use `persist_actions=False` and `dry_run=True`
- `prioritized_actions` in the final report are summaries only — no approval/execution state
- No auto-approve or auto-execute behavior introduced

---

## Star topology verification

- `assert_star_topology()` and empty `SPECIALIST_PEER_CALL_PATHS` enforced
- HTTP log shows coordinator → sales/content/support `/run` only
- No specialist-to-specialist HTTP calls
- Static peer-URL tests from Step 10.1 remain passing

---

## Implementation summary

### Merge module (`agents/coordinator/merge.py`)

Builds the Django-compatible daily report document:

- Extracts `sales_summary` from context bundle
- Maps sales `recommendations` → `prioritized_actions` (priority sort + SKU dedupe)
- Maps content `drafts` → `content_suggestions`
- Maps support output → `support_insights`
- Generates `next_steps` from available sections
- Serializes coordinator `warnings` into report `warnings[]`
- Preserves `missing_sections` / `partial` for timeout compatibility

### Coordinator nodes (`agents/coordinator/nodes.py`)

- Specialist-specific payloads filtered to each agent's Pydantic request schema
- Support payload derives `customer_message` / `channel` from sanitized context threads
- Content payload maps `products` and `store_context` from context bundle

---

## Files changed

| File | Change |
|------|--------|
| `agents/coordinator/merge.py` | **Created** — daily report merge helpers |
| `agents/coordinator/nodes.py` | **Updated** — specialist payloads + merge integration |
| `agents/coordinator/workflow.py` | **Updated** — Step 10.4 note |
| `agents/coordinator/tests/integration_harness.py` | **Created** — router + Django recording mock |
| `agents/coordinator/tests/test_full_graph_integration.py` | **Created** — full/partial graph integration tests |
| `docs/phases/step-10.4.md` | **Created** — this document |

---

## Tests added

| Test module | Coverage |
|-------------|----------|
| `test_full_graph_integration.py` | Success path, partial failure, merge dedupe, star topology, action workflow, schema compatibility |
| `integration_harness.py` | Shared Django mock + specialist TestClient router |

---

## Verification commands run

```bash
python -m unittest agents.coordinator.tests.test_full_graph_integration -v
python -m unittest discover -s agents/coordinator/tests -v
python -m unittest \
  agents.coordinator.tests.test_star_topology \
  agents.coordinator.tests.test_node_timeouts \
  agents.coordinator.tests.test_agent_output_persistence \
  agents.coordinator.tests.test_full_graph_integration -v
```

---

## Results

| Suite | Result |
|-------|--------|
| Step 10.4 full graph integration (9 tests) | **Passed** |
| Full coordinator test suite (74 tests) | **Passed** |
| Step 10.1 star topology | **Passed** (preserved) |
| Step 10.2 node timeouts | **Passed** (preserved) |
| Step 10.3 AgentOutput persistence | **Passed** (preserved) |

---

## Known limitations

- `POST /workflows/daily-report` remains the Phase 6.4 stub; Celery still receives an immediate `accepted` response without running the full graph in-process
- Integration tests use a Django HTTP test double, not a live Postgres `ReportRun` row (completion is verified via mock response and workflow state)
- LangGraph compiled graph wiring is still deferred; the sequential `run_daily_report_workflow()` runner is the integration entrypoint
- Specialist HTTP failures (non-timeout 4xx/5xx) are not yet converted to partial-report warnings — only timeout partial behavior is covered
- No real Celery worker or docker-compose multi-service smoke test in this step

---

## Phase 10 completion decision

**Phase 10 is complete** against the documented acceptance criteria:

| Criterion | Status |
|-----------|--------|
| Star topology (10.1) | Met |
| Per-node timeouts (10.2) | Met |
| AgentOutput persistence (10.3) | Met |
| Full graph mock integration (10.4) | Met |
| Mock LLM across services, no API keys | Met |
| Final report sections + `agent_outputs_ref` | Met |
| Partial failure in `warnings[]` | Met |
| No auto-approve / execute actions | Met |

Phase 11 (frontend dashboard) and Phase 12 (Prestia demo polish) remain out of scope and were not implemented.
