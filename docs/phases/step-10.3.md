# Step 10.3 — Coordinator AgentOutput Persistence

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Persist intermediate specialist agent outputs from the coordinator workflow as `AgentOutput` records through Django internal APIs, capture returned IDs in coordinator state, and include them in the final daily report payload.

---

## Scope

### In scope

- Coordinator helper module for safe AgentOutput persistence
- `DjangoClient.create_agent_output()` → `POST /internal/ai/agent-outputs/`
- Persistence after successful `run_sales`, `run_content`, and `run_support` nodes
- `agent_outputs_ref` collected in coordinator state and merged report
- `agent_output_ids` forwarded on report completion
- Safe handling of persistence failures and specialist timeouts
- Deterministic unit tests with mocked Django client and specialist responses
- Preservation of Step 10.1 star topology and Step 10.2 per-node timeout behavior

### Non-goals

| Area | Deferred work |
|------|----------------|
| **Step 10.4** | Full cross-service graph integration test with mock LLM |
| — | LangGraph compiled graph wiring |
| — | Wiring `POST /workflows/daily-report` to the full workflow |
| — | Backend model/migration changes |
| — | Failure/timeout-specific AgentOutput record types (not supported by current API) |
| — | Frontend/dashboard changes |

**Step 10.4 full graph integration testing was not implemented in this step.**

---

## Implementation summary

### Persistence helper (`agents/coordinator/agent_output_persistence.py`)

- `sanitize_specialist_output_payload()` — strips untrusted `tenant_id` / `store_id` from specialist payloads
- `build_agent_output_request()` — builds the Django internal API body using trusted `report_run_id` and node mapping
- `persist_specialist_agent_output()` — calls `DjangoClient.create_agent_output()` and returns `AgentOutputPersistenceResult`
- Safe warnings:
  - `agent_output_persistence_failed` — Django persistence error; workflow continues with in-memory specialist result
  - `agent_output_not_persisted` — specialist node timeout/failure; no fabricated output persisted

### Coordinator workflow wiring

After each successful specialist node:

1. Specialist output is stored on coordinator state (`sales_output`, `content_output`, or `support_output`)
2. Sanitized output is persisted via Django
3. Returned `id` is appended to `state.agent_outputs_ref`

`node_merge` includes `agent_outputs_ref` in the merged report document.

`node_submit` passes:

- `report.agent_outputs_ref` inside the merged report payload
- top-level `agent_output_ids` to `DjangoClient.complete_report_run()` for backend validation/linking

Star topology and timeout behavior from Steps 10.1 and 10.2 are unchanged.

---

## AgentOutput persistence contract

**Endpoint:** `POST /internal/ai/agent-outputs/`

**Request body (coordinator-built):**

```json
{
  "output_type": "sales_analysis",
  "payload": {
    "summary": "Sales section summary.",
    "metadata": { "agent_name": "sales-agent" }
  },
  "metadata": {
    "source_agent_name": "sales-agent",
    "coordinator_node": "run_sales"
  },
  "report_run_id": "11111111-1111-4111-8111-111111111111"
}
```

| Specialist node | `output_type` | `metadata.source_agent_name` |
|-----------------|---------------|--------------------------------|
| `run_sales` | `sales_analysis` | `sales-agent` |
| `run_content` | `content_suggestions` | `content-agent` |
| `run_support` | `support_insights` | `support-agent` |

**Scope rules:**

- `tenant_id` and `store_id` are never taken from specialist payloads
- `report_run_id` comes from trusted coordinator workflow state
- Django sets persisted `agent_name` from the coordinator service JWT (`coordinator-agent`)
- Specialist identity is recorded in request `metadata.source_agent_name`

**Response used by coordinator:**

```json
{
  "id": "agent-output-uuid",
  "agent_name": "coordinator-agent",
  "output_type": "sales_analysis",
  "report_run_id": "11111111-1111-4111-8111-111111111111"
}
```

---

## How `agent_outputs_ref` is collected and submitted

1. Each successful specialist persistence appends the returned UUID string to `DailyReportWorkflowState.agent_outputs_ref`
2. `node_merge` copies the list into `merged_report["agent_outputs_ref"]`
3. `node_submit` calls:

```python
client.complete_report_run(
    report_run_id,
    report=merged_report,
    agent_output_ids=agent_outputs_ref,
)
```

---

## Persistence failure behavior

- Django client errors do **not** crash the workflow when the specialist result is already available
- A structured `agent_output_persistence_failed` warning is appended to coordinator state
- The original specialist output remains on state for partial merge/submit
- Warnings contain no raw HTTP bodies, JWTs, headers, or full payloads

---

## Timeout/failure output behavior

The current Django `AgentOutput` API accepts successful structured outputs only; there is no supported status/error record type for timeout or failure snapshots.

Therefore:

- Timed-out specialist nodes (Step 10.2 `specialist_node_timeout` warning) do **not** persist fabricated outputs
- An additional `agent_output_not_persisted` warning explains that persistence was skipped
- Partial merge/submit continues when context and other specialist sections are available

---

## Known limitations

- **Idempotency:** The backend has no uniqueness constraint on `(report_run, coordinator_node)` AgentOutput records. Retried workflow runs may create duplicate AgentOutput rows unless a future backend idempotency key is added.
- **Persisted `agent_name`:** Records are stored under `coordinator-agent` because the coordinator service JWT performs the write; specialist identity is preserved in `metadata.source_agent_name`.
- **Report completion payload:** The current merge scaffold does not yet populate the full Phase 0 daily report schema (`generated_at`, `period`, etc.); only `agent_outputs_ref` wiring was added in this step.

---

## Files changed

| Path | Action |
|------|--------|
| `agents/coordinator/agent_output_persistence.py` | Created — persistence helper |
| `agents/coordinator/nodes.py` | Updated — persist after specialist success; merge/submit refs |
| `agents/coordinator/state.py` | Updated — `agent_outputs_ref` field |
| `agents/coordinator/workflow.py` | Updated — docstring for Step 10.3 |
| `agents/shared/django_client/client.py` | Updated — `create_agent_output()`, `complete_report_run(agent_output_ids=...)` |
| `agents/coordinator/tests/test_agent_output_persistence.py` | Created — Step 10.3 tests |
| `agents/coordinator/tests/test_node_timeouts.py` | Updated — mock `create_agent_output`, timeout warning count |
| `agents/shared/tests/test_django_client.py` | Updated — `create_agent_output` POST test |
| `docs/phases/step-10.3.md` | Created — this document |

---

## Tests added

`agents/coordinator/tests/test_agent_output_persistence.py`:

- Successful sales/content/support AgentOutput persistence
- Returned IDs captured in coordinator state
- Final merged report and submit payload include `agent_outputs_ref` / `agent_output_ids`
- Persistence failure creates structured warning without discarding specialist output
- Timeout skips persistence with `agent_output_not_persisted` warning
- Untrusted `tenant_id` / `store_id` stripped from persistence payloads
- Full workflow integration with three persisted refs

Existing Step 10.1 and 10.2 tests updated/verified to remain passing.

---

## Verification commands run

```bash
python -m unittest agents.coordinator.tests.test_agent_output_persistence -v
python -m unittest agents.coordinator.tests.test_node_timeouts -v
python -m unittest agents.coordinator.tests.test_star_topology -v
python -m unittest agents.shared.tests.test_django_client -v
```

---

## Results

All focused verification tests passed (69 tests, 0 failures):

```
python -m unittest agents.coordinator.tests.test_agent_output_persistence \
  agents.coordinator.tests.test_node_timeouts \
  agents.coordinator.tests.test_star_topology \
  agents.shared.tests.test_django_client -v
# Ran 69 tests in 0.710s — OK
```

---

## Explicit deferral

**Step 10.4 — full graph integration test with mock LLM across services — was not implemented in this step.**
