# Step 10.5 — Real Coordinator Endpoint & Celery Completion Wiring

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Replace the Phase 6.4 coordinator daily-report stub with real workflow execution and align Celery so `ReportRun` completion is driven by the coordinator workflow submitting to Django internal report completion APIs — not by a generic HTTP 2xx stub response.

---

## Scope

### In scope

- Real `POST /workflows/daily-report` endpoint invoking `run_daily_report_workflow()`
- Safe request/response schemas and workflow state mapping
- Service JWT and `X-Request-ID` / request-body correlation forwarding
- Coordinator-driven final report submission via existing Django client (`complete_report_run`)
- Celery `reports.generate_daily` handoff relying on coordinator + Django completion
- Rejection of legacy stub `accepted` responses
- Focused endpoint, coordinator-client, and Celery task tests
- Preservation of Steps 10.1–10.4 behavior

### Non-goals

| Area | Deferred work |
|------|----------------|
| **Step 10.6** | LangGraph compiled graph wiring |
| **Step 10.6** | Parallel specialist execution |
| **Step 10.7** | DB-backed final E2E verification and Phase 10 closure |
| **Phase 11** | Frontend/dashboard UI |
| **Phase 12** | Prestia demo polish |
| — | Real LLM providers or API keys |
| — | Real Instagram publish/send or external side effects |
| — | Direct database access from agents |
| — | Auto-approval or action execution |

**Step 10.6 LangGraph/parallelism was not implemented in this step.**  
**Step 10.7 DB-backed final E2E closure was not implemented in this step.**

---

## Implementation summary

### Coordinator endpoint (`agents/coordinator/app/main.py`)

- `POST /workflows/daily-report` validates `DailyReportJobRequest`
- Extracts Bearer service JWT and correlation ID (`X-Request-ID` header preferred over body `request_id`)
- Maps payload into `DailyReportWorkflowState`
- Invokes `run_daily_report_workflow()` via `execute_daily_report_workflow()`
- Returns `DailyReportWorkflowResponse` with `status=completed` or `status=failed`
- Unexpected exceptions are caught and converted to a sanitized failed response

### Workflow endpoint helpers (`agents/coordinator/app/workflow_endpoint.py`)

- `build_workflow_state_from_request()` — trusted `report_run_id` plus forwarded JWT/request ID
- `build_workflow_response()` — maps workflow state to safe HTTP response
- `execute_daily_report_workflow()` — runner entrypoint used by FastAPI route

### Celery handoff (`backend/operations/tasks.py`)

- Calls `CoordinatorDailyReportClient.trigger_daily_report()` and parses structured workflow status
- On `status=completed`: succeeds only when Django `ReportRun` is already `completed` (coordinator submitted via internal API)
- On `status=failed`: marks `ReportRun` failed with sanitized coordinator message
- On legacy `status=accepted` or HTTP/parse errors: marks `ReportRun` failed
- Removed skeleton `mark_completed_if_still_running()` fallback from the success path

### Coordinator HTTP client (`backend/operations/coordinator_client.py`)

- Returns `CoordinatorDailyReportResult` with parsed `workflow_status`, `report_run_id`, and `message`
- Rejects legacy stub `accepted` responses explicitly
- Validates `report_run_id` matches the requested run

---

## Coordinator endpoint request/response contract

### Request

`POST /workflows/daily-report`

Headers (optional unless noted):

- `Authorization: Bearer <service_jwt>` — forwarded into workflow/Django/specialist clients
- `X-Request-ID: <correlation-id>` — preferred correlation ID

Body:

```json
{
  "report_run_id": "<uuid>",
  "tenant_id": "<uuid>",
  "store_id": "<uuid>",
  "context_ref": {
    "type": "report_run",
    "id": "<uuid>"
  },
  "request_id": "<optional>",
  "period": "<optional>",
  "requested_by": "<optional>"
}
```

`context_ref.id` must match `report_run_id`.

### Success response (`status=completed`)

```json
{
  "status": "completed",
  "workflow": "daily_report",
  "report_run_id": "<uuid>",
  "message": "Daily report workflow completed.",
  "warnings": [],
  "partial": false
}
```

`partial=true` when the merged report was produced with missing specialist sections (Step 10.2/10.4 partial behavior preserved).

### Failure response (`status=failed`)

```json
{
  "status": "failed",
  "workflow": "daily_report",
  "report_run_id": "<uuid>",
  "message": "Context fetch timed out.",
  "warnings": [
    {
      "code": "critical_node_timeout",
      "message": "Context fetch timed out."
    }
  ],
  "partial": false
}
```

Messages and warnings are sanitized — no JWTs, raw HTTP bodies, prompts, or customer PII.

---

## Celery/coordinator handoff behavior

1. `ReportRun` transitions `queued` → `running`
2. Celery POSTs the Phase 5 payload to coordinator with service JWT
3. Coordinator runs the full sequential workflow (fetch → sales → content → support → merge → submit)
4. Coordinator calls `POST /internal/ai/report-runs/{id}/complete/` through `DjangoClient.complete_report_run()`
5. Coordinator returns `status=completed` or `status=failed`
6. Celery accepts completion only when:
   - coordinator response `status=completed`, **and**
   - Django `ReportRun.status=completed`

Legacy stub `{"status":"accepted"}` responses are rejected by the coordinator client and mark the run failed.

---

## Failure behavior

| Scenario | Celery / `ReportRun` outcome |
|----------|------------------------------|
| Coordinator HTTP non-2xx | `failed` with sanitized HTTP error message |
| Coordinator connection/timeout error | `failed` with sanitized transport error |
| Legacy stub `accepted` response | `failed` — stub completion is not accepted |
| Coordinator `status=failed` | `failed` with coordinator `message` |
| Coordinator `status=completed` but Django still `running` | `failed` — coordinator incompleteness is not masked |
| Coordinator `status=completed` and Django `completed` | success |
| Terminal `ReportRun` before task | skipped (unchanged Step 5.3 behavior) |

---

## Files changed

| File | Change |
|------|--------|
| `agents/coordinator/app/main.py` | Real workflow endpoint |
| `agents/coordinator/app/workflow_endpoint.py` | **Created** — mapping, execution, logging helpers |
| `agents/coordinator/app/schemas.py` | `DailyReportWorkflowResponse` replaces stub response |
| `agents/coordinator/workflow.py` | Step 10.5 note |
| `agents/coordinator/tests/test_daily_report_endpoint.py` | **Created** — endpoint contract tests |
| `agents/coordinator/tests/test_daily_report_stub.py` | **Removed** — replaced by endpoint tests |
| `backend/operations/coordinator_client.py` | Structured response parsing; stub rejection |
| `backend/operations/tasks.py` | Coordinator-driven completion verification |
| `backend/operations/services.py` | Document legacy skeleton helper |
| `backend/operations/tests/test_generate_daily_task.py` | Updated Celery/coordinator tests |
| `backend/operations/tests/test_coordinator_integration.py` | Updated integration handoff tests |
| `backend/operations/tests/mock_coordinator_server.py` | Completed-response helper; request callback fixes |
| `agents/shared/tests/test_phase6_scaffold.py` | Updated coordinator endpoint expectation |
| `docs/phases/step-10.5.md` | **Created** — this document |

---

## Tests added

| Module | Coverage |
|--------|----------|
| `test_daily_report_endpoint.py` | Real workflow invocation, state mapping, JWT/correlation forwarding, completed/failed responses, validation, sanitized errors |
| `test_generate_daily_task.py` | Stub rejection, coordinator-driven completion, workflow failure, Django mismatch failure |
| `test_coordinator_integration.py` | HTTP payload/JWT contract, success with coordinator-driven Django completion, stub/failed/timeout/500 paths |

---

## Verification commands run

```bash
python -m unittest agents.coordinator.tests.test_daily_report_endpoint -v
python -m unittest \
  agents.coordinator.tests.test_star_topology \
  agents.coordinator.tests.test_node_timeouts \
  agents.coordinator.tests.test_agent_output_persistence \
  agents.coordinator.tests.test_full_graph_integration \
  agents.coordinator.tests.test_daily_report_endpoint -v
cd backend && python manage.py test \
  operations.tests.test_generate_daily_task \
  operations.tests.test_coordinator_integration -v 2
```

---

## Results

| Suite | Result |
|-------|--------|
| Step 10.5 endpoint tests (15 tests) | **Passed** |
| Step 10.1 star topology | **Passed** (preserved) |
| Step 10.2 node timeouts | **Passed** (preserved) |
| Step 10.3 AgentOutput persistence | **Passed** (preserved) |
| Step 10.4 full graph integration | **Passed** (preserved) |
| Backend Celery/coordinator tests (22 tests) | **Passed** |

---

## Known limitations

- The coordinator endpoint runs the sequential `run_daily_report_workflow()` runner — LangGraph compiled graph wiring remains deferred to Step 10.6
- Specialist nodes still run sequentially; parallel fan-out is deferred to Step 10.6
- Integration tests simulate coordinator-driven Django completion in the Celery thread after HTTP returns — full in-container coordinator → Django E2E without test hooks belongs to Step 10.7
- `mark_completed_if_still_running()` remains in `ReportRunService` as a legacy helper but is no longer used by `reports.generate_daily`
- Endpoint tests mock the workflow runner for determinism; full in-process coordinator + specialist + Django HTTP doubles remain in Step 10.4 integration tests

---

## Explicit deferrals

- **Step 10.6 — LangGraph workflow and parallel specialist execution — was not implemented in this step.**
- **Step 10.7 — DB-backed final E2E verification and Phase 10 closure — was not implemented in this step.**
