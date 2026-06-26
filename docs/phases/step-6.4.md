# Step 6.4 — Coordinator Stub Endpoint Accepting Report Job

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Expose a minimal, deterministic FastAPI endpoint on `coordinator-agent` that accepts the daily report job payload sent by the Phase 5 Celery task (`reports.generate_daily`). The endpoint validates the request, returns structured JSON, and does **not** run LangGraph, specialist agents, or real LLM calls.

This completes **Phase 6 — Agent Scaffold & LLM Abstraction** at the coordinator boundary. Specialist agent stubs and LangGraph orchestration remain for later phases.

---

## Scope of this step

- `POST /workflows/daily-report` stub on `coordinator-agent`
- Pydantic request/response models compatible with Phase 5 Celery payload
- Reuse of shared `AgentWarning` from Step 6.3
- Optional `Authorization` and `X-Request-ID` header handling (no full JWT validation)
- Docker build updates so the coordinator container can import `agents.shared`
- Focused unit tests under `agents/coordinator/tests/`
- Cursor scope rule at `.cursor/rules/step-6.4-coordinator-stub-endpoint.mdc`
- This documentation file

**Not in scope:** Sales/content/support agent logic, LangGraph, real daily report merging, Django `report-runs/complete/`, real LLM providers, or production-grade service JWT validation inside FastAPI.

---

## Endpoints

### Health

`GET /health`

```json
{
  "status": "ok",
  "service": "coordinator-agent"
}
```

### Daily report stub

`POST /workflows/daily-report`

Accepts the same semantic payload built by `CoordinatorDailyReportClient.build_payload()` in Django.

---

## Request schema

Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `report_run_id` | UUID | Report run identifier |
| `tenant_id` | UUID | Tenant scope |
| `store_id` | UUID | Store scope |
| `context_ref` | object | Must be `{ "type": "report_run", "id": "<uuid>" }` where `id` matches `report_run_id` |

Optional fields (accepted when present):

| Field | Type |
|-------|------|
| `request_id` | string |
| `period` | string |
| `requested_by` | string |

Example (matches Phase 5 Celery contract):

```json
{
  "report_run_id": "11111111-1111-4111-8111-111111111111",
  "tenant_id": "22222222-2222-4222-8222-222222222222",
  "store_id": "33333333-3333-4333-8333-333333333333",
  "context_ref": {
    "type": "report_run",
    "id": "11111111-1111-4111-8111-111111111111"
  }
}
```

Invalid payloads return HTTP `422` with a FastAPI/Pydantic `detail` array.

---

## Response schema

Deterministic success response (HTTP `200`):

```json
{
  "status": "accepted",
  "workflow": "daily_report",
  "report_run_id": "11111111-1111-4111-8111-111111111111",
  "message": "Coordinator stub accepted the daily report job.",
  "warnings": [
    {
      "code": "stub_mode",
      "message": "Real LangGraph orchestration is not implemented yet."
    }
  ]
}
```

Phase 5 only requires a **2xx HTTP status** from the coordinator call; the Celery task does not parse this JSON body yet. The shape above is stable for Phase 10 orchestration work.

---

## Header / auth behavior

| Header | Behavior |
|--------|----------|
| `Authorization` | Optional. When present, must use `Bearer <token>` or the endpoint returns `401`. Full JWT signature/claim validation is **deferred** to a later phase. |
| `X-Request-ID` | Optional. Accepted for correlation; may appear in structured logs only (never echoed with secrets). |

Logging records safe identifiers (`report_run_id`, `tenant_id`, `store_id`, `auth_present`, `auth_scheme`, `request_id`) and **never** logs raw token values.

---

## Connection to Phase 5 Celery task

Flow:

1. Manager triggers `POST /api/reports/generate/` → queued `ReportRun`.
2. Celery task `reports.generate_daily` marks the run `running`.
3. `CoordinatorDailyReportClient.trigger_daily_report()` POSTs to `COORDINATOR_DAILY_REPORT_URL` (default `http://coordinator-agent:8100/workflows/daily-report`) with:
   - JSON body from `build_payload()`
   - `Authorization: Bearer <service-jwt>` from `mint_service_jwt()`
4. On HTTP 2xx, the task marks `ReportRun` as `completed`.
5. On failure/timeout/non-2xx, the task marks `ReportRun` as `failed`.

The stub endpoint satisfies step 4 without performing real orchestration or Django writes.

---

## Files changed

| Path | Change |
|------|--------|
| `agents/coordinator/app/main.py` | Added `POST /workflows/daily-report`, header handling, validation handler |
| `agents/coordinator/app/schemas.py` | Request/response Pydantic models |
| `agents/coordinator/app/__init__.py` | Package marker |
| `agents/coordinator/__init__.py` | Package marker |
| `agents/coordinator/requirements.txt` | Added `pydantic`, `httpx` |
| `agents/coordinator/Dockerfile` | Build from `agents/` context; copy `shared/`; `PYTHONPATH=/app` |
| `agents/coordinator/tests/test_daily_report_stub.py` | Endpoint unit tests |
| `agents/coordinator/tests/__init__.py` | Test package marker |
| `docker-compose.yml` | Coordinator build `context: ./agents`, `dockerfile: coordinator/Dockerfile` |
| `.cursor/rules/step-6.4-coordinator-stub-endpoint.mdc` | Step scope rule |
| `docs/phases/step-6.4.md` | This document |

No new environment variables were required. Existing `COORDINATOR_AGENT_URL` / compose service DNS remain sufficient.

---

## Tests added

`agents/coordinator/tests/test_daily_report_stub.py`:

- `GET /health` returns 200
- Valid Phase 5 payload returns `status`, `workflow`, `report_run_id`
- Response is deterministic across repeated calls
- Missing `report_run_id` returns 422
- Invalid `context_ref.type` returns 422
- `context_ref.id` mismatch with `report_run_id` returns 422
- `Authorization: Bearer ...` is accepted
- Requests without `Authorization` are accepted
- Non-Bearer `Authorization` returns 401
- `X-Request-ID` is accepted
- Response does not expose raw tokens or optional PII fields
- Logger extra fields do not include raw tokens
- `stub_mode` warning is present

Phase 5 mock coordinator integration tests are unchanged; they continue to use an in-process mock HTTP server.

---

## Validation commands

Install agent dependencies (local, once):

```bash
pip install -r agents/requirements.txt
```

Run coordinator stub tests:

```bash
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_daily_report_stub -v
```

Run all agent unit tests:

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

Build and start the stack:

```bash
docker compose up --build
```

Check services:

```bash
docker compose ps
docker compose logs coordinator-agent
```

Smoke-test health:

```bash
curl -s http://localhost:8100/health
```

Smoke-test daily report stub:

```bash
curl -s -X POST http://localhost:8100/workflows/daily-report \
  -H 'Content-Type: application/json' \
  -d '{
    "report_run_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "store_id": "33333333-3333-4333-8333-333333333333",
    "context_ref": {"type": "report_run", "id": "11111111-1111-4111-8111-111111111111"}
  }'
```

Run Django backend tests (Phase 5 flows unchanged):

```bash
docker compose exec backend python manage.py test
```

---

## What is intentionally stubbed

- LangGraph workflow execution
- Calls to `sales-agent`, `content-agent`, `support-agent`
- Fetching AI context bundle from Django
- Completing report runs via `/internal/ai/report-runs/{id}/complete/`
- Merging agent outputs into a `DailyReport`
- Real LLM provider calls
- Full service JWT validation inside FastAPI (Bearer scheme check only when header is sent)

---

## What is intentionally not implemented

- Phase 7 — Sales agent business logic
- Phase 8 — Content agent business logic
- Phase 9 — Support agent business logic
- Phase 10 — Coordinator LangGraph orchestration and real report completion
- `LLMProvider` abstraction wiring in coordinator
- Django writes from the coordinator stub

---

## Phase 6 completion note

With Steps 6.1–6.4 complete, the shared agent foundation is in place:

| Step | Deliverable |
|------|-------------|
| 6.1 | `AI_OUTPUT_LANGUAGE` helper |
| 6.2 | Shared `DjangoClient` with JWT and correlation ID forwarding |
| 6.3 | Shared Pydantic validation and base schemas |
| 6.4 | Coordinator daily report stub endpoint |

Phase 7+ can add specialist agent `/run` endpoints and Phase 10 can replace the stub with real LangGraph orchestration while reusing shared modules.

---

## Next phases

| Phase | Focus |
|-------|-------|
| **7** | Sales Agent — analysis logic and structured recommendations |
| **8** | Content Agent — captions, product copy, campaign drafts |
| **9** | Support Agent — DM analysis and safe reply drafts |
| **10** | Coordinator & LangGraph — real orchestration, context fetch, agent delegation, Django completion |
