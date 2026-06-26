# Step 5.2 — Daily Report Celery Task Lifecycle

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Implement the minimal asynchronous daily report lifecycle: create a queued `ReportRun`, transition it to `running`, call the coordinator-agent over HTTP, and mark the run `completed` or `failed` based on the coordinator response.

This step wires the Celery task skeleton and dashboard trigger. It does **not** implement duplicate-run prevention, real LangGraph orchestration, or specialist agents.

---

## Scope of this step

- `reports.generate_daily` Celery task with `ReportRun` status transitions
- Coordinator HTTP client using environment-configured URL, path, and timeout
- Service JWT minting for coordinator requests (Phase 2 utility)
- `POST /api/reports/generate/` dashboard trigger (manager auth, store-scoped)
- Focused unit/API tests with mocked coordinator HTTP calls
- Environment variables in `.env.example`
- Cursor scope rule at `.cursor/rules/step-5.2-report-task-lifecycle.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `backend/config/settings.py` | Updated — coordinator URL/path/timeout settings |
| `backend/operations/services.py` | Updated — `mark_running`, `mark_failed`, `mark_completed_if_still_running` |
| `backend/operations/coordinator_client.py` | Created — coordinator HTTP client |
| `backend/operations/tasks.py` | Created — `reports.generate_daily` task |
| `backend/operations/views.py` | Updated — `ReportGenerateView` |
| `backend/operations/urls.py` | Updated — `reports/generate/` route |
| `backend/operations/tests/test_generate_daily_task.py` | Created — task lifecycle tests |
| `backend/operations/tests/test_report_generate_api.py` | Created — API trigger tests |
| `.env.example` | Updated — coordinator path and timeout variables |
| `.cursor/rules/step-5.2-report-task-lifecycle.mdc` | Scope rule for this step |
| `docs/phases/step-5.2.md` | Created — this document |

---

## ReportRun lifecycle implemented in this step

```
queued  →  running  →  completed   (coordinator HTTP 2xx, skeleton completion)
                   └→  failed      (coordinator HTTP error, timeout, or connection failure)
```

| Status | When set |
|--------|----------|
| `queued` | Created by `POST /api/reports/generate/` |
| `running` | Celery task starts processing a non-terminal run |
| `completed` | Coordinator HTTP succeeds and run is still `running` (see completion behavior below) |
| `failed` | Coordinator call fails; `error_message` stores a safe summary |

Terminal runs (`completed`, `failed`) are not modified if the task is retried.

---

## Completion behavior (important)

Phase 4 already provides `POST /internal/ai/report-runs/{id}/complete/`, which transitions `running` → `completed` and persists a `DailyReport`.

**Step 5.2 chosen behavior:**

1. After a successful coordinator HTTP call, the task refreshes the `ReportRun`.
2. If the run is **still** `running`, the task marks it `completed` as a **skeleton fallback** (for mocked coordinators that return 2xx without calling the internal complete API).
3. If the coordinator (or a synchronous stub) already called the internal complete API and set `completed`, the task **does not** double-write status.

In Phase 10, the real coordinator will call the internal complete endpoint with the final report payload. The Celery task will observe `completed` after refresh and skip skeleton completion.

---

## Celery task

| Item | Value |
|------|-------|
| Task name | `reports.generate_daily` |
| Module | `backend/operations/tasks.py` |
| Input | `report_run_id` (UUID string) |
| Return | `{"status": "...", "report_run_id": "..."}` or skip reason |

---

## Coordinator HTTP endpoint and payload

**URL:** built from settings, not hardcoded:

```
{COORDINATOR_AGENT_URL}{COORDINATOR_DAILY_REPORT_PATH}
```

Default: `http://coordinator-agent:8100/workflows/daily-report`

**Method:** `POST`

**Headers:**

- `Content-Type: application/json`
- `Authorization: Bearer <service_jwt>` (minted via Phase 2 `mint_service_jwt` for `coordinator-agent`)

**Request body:**

```json
{
  "report_run_id": "<uuid>",
  "tenant_id": "<uuid>",
  "store_id": "<uuid>",
  "context_ref": {
    "type": "report_run",
    "id": "<uuid>"
  }
}
```

**Success:** HTTP 2xx  
**Failure:** non-2xx, timeout, or connection error → `ReportRun.status = failed`

Logs include only safe identifiers: `report_run_id`, `tenant_id`, `store_id`, HTTP status, duration, and error class. Raw request/response bodies are not logged.

---

## Dashboard API trigger

### `POST /api/reports/generate/`

- **Auth:** session-authenticated manager (or staff)
- **Scope:** user's `tenant` and `store` (store required on user)
- **Behavior:** creates `ReportRun(status=queued)`, enqueues `reports.generate_daily`
- **Response (201):**

```json
{
  "report_run_id": "<uuid>",
  "status": "queued",
  "task_id": "<celery-task-id>"
}
```

Duplicate concurrent runs per store are **not** prevented in this step (Step 5.3).

---

## Environment variables added

| Variable | Example | Used by |
|----------|---------|---------|
| `COORDINATOR_AGENT_URL` | `http://coordinator-agent:8100` | Django settings, coordinator client |
| `COORDINATOR_DAILY_REPORT_PATH` | `/workflows/daily-report` | Django settings, coordinator client |
| `COORDINATOR_HTTP_TIMEOUT_SECONDS` | `30` | Coordinator HTTP client |

`COORDINATOR_AGENT_URL` was already present in `.env.example`; path and timeout were added in this step.

---

## Error handling behavior

| Failure | ReportRun result | `error_message` |
|---------|------------------|-----------------|
| Coordinator HTTP 4xx/5xx | `failed` | e.g. `Coordinator returned HTTP 502.` |
| Connection / DNS / timeout (`URLError`) | `failed` | e.g. `Coordinator request failed: ...` |
| Run already `completed` or `failed` | unchanged (task skips) | preserved |
| Run not found | task returns skip (no DB change) | — |

---

## Validation commands

### Start the stack

```bash
cp .env.example .env   # if you do not already have .env
docker compose up --build
```

### Check services

```bash
docker compose ps
```

Expect `backend`, `celery-worker`, `redis`, and `postgres` to be running.

### Inspect worker logs

```bash
docker compose logs celery-worker
```

Look for registered task: `reports.generate_daily`

### Inspect backend logs

```bash
docker compose logs backend
```

### Run Step 5.2 tests

```bash
docker compose exec backend python manage.py test operations.tests.test_generate_daily_task operations.tests.test_report_generate_api
```

Or locally from `backend/`:

```bash
python manage.py test operations.tests.test_generate_daily_task operations.tests.test_report_generate_api
```

### Example: trigger report generation (after login)

```bash
# 1. Login (session cookie)
curl -c /tmp/cookies.txt -X POST http://localhost/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"manager@prestia.local","password":"<demo-password>"}'

# 2. Generate report
curl -b /tmp/cookies.txt -X POST http://localhost/api/reports/generate/ \
  -H "Content-Type: application/json"
```

Replace credentials with your seeded manager account. The manager user must have a `store` assigned.

---

## What is intentionally NOT implemented in this step

- Duplicate concurrent report run prevention per store (Step 5.3)
- Locking or active-run database constraints (Step 5.3)
- Mock coordinator integration test server (Step 5.4)
- `actions.execute` Celery task
- Celery beat stale-run cleanup schedule
- Real LangGraph workflow in coordinator-agent
- Specialist agents (sales, content, support)
- LLM provider abstraction
- Frontend report generation UX
- PII context bundle assembly inside the Celery task (coordinator fetches context via internal APIs in later phases)

---

## Next steps

- **Step 5.3:** Prevent duplicate concurrent runs per store when triggering report generation.
- **Step 5.4:** Integration test with a mock coordinator HTTP server in CI.
