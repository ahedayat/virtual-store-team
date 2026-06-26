# Step 5.3 — Prevent Duplicate Concurrent Report Runs

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Ensure each store can have at most one **active** daily report run at a time. Duplicate generation requests while a run is `queued` or `running` return a controlled HTTP `409 Conflict` response and do **not** enqueue a Celery task.

---

## Why duplicate prevention is needed

Without a guard, a manager (or double-click on the dashboard) could create multiple concurrent `ReportRun` records for the same store. That would:

- Enqueue duplicate Celery tasks against the coordinator
- Produce overlapping agent workflows and conflicting writes
- Make the dashboard history confusing

Step 5.3 adds tenant/store-scoped duplicate detection with a database-level safety net for concurrent requests.

---

## Active and terminal statuses

The project reuses existing `ReportRun` status constants from `operations.constants`:

| Category | Statuses |
|----------|----------|
| **Active** (block new generation) | `queued`, `running` |
| **Terminal** (allow new generation) | `completed`, `failed` |

There is no `cancelled` status on `ReportRun` in the current model. Action records have `cancelled`, but report runs do not.

Constants:

- `REPORT_RUN_ACTIVE_STATUSES`
- `REPORT_RUN_TERMINAL_STATUSES`

---

## Implementation strategy

### Centralized service

`ReportRunService.create_queued_run_for_store(tenant, store)` in `backend/operations/services.py`:

1. Validates tenant/store scope.
2. Runs inside `transaction.atomic()`.
3. Checks for an existing active run (`queued` or `running`) for the same tenant/store.
4. Creates a new `ReportRun` with status `queued` only when none exists.
5. On `IntegrityError` (concurrent race), fetches the winning active run and returns a duplicate result.

Returns `CreateQueuedRunResult(created: bool, report_run: ReportRun)`.

### Database constraint

Partial unique constraint on `ReportRun`:

```python
UniqueConstraint(
    fields=["tenant", "store"],
    condition=Q(status__in=REPORT_RUN_ACTIVE_STATUSES),
    name="unique_active_report_run_per_store",
)
```

Migration: `operations/migrations/0003_unique_active_report_run_per_store.py`

This guarantees at most one active run per tenant/store even if two requests pass the application check simultaneously.

### API endpoint

`POST /api/reports/generate/` (`ReportGenerateView`) now delegates to the service instead of creating `ReportRun` directly.

| Case | HTTP status | Celery enqueued? | Response fields |
|------|-------------|------------------|-----------------|
| New run created | `202 Accepted` | Yes | `report_run_id`, `status`, `task_id` |
| Active run exists | `409 Conflict` | No | `detail`, `existing_report_run_id`, `status`, `created_at` |

Duplicate responses are explicit so the frontend can show “report already in progress.”

---

## Celery enqueue behavior

`generate_daily.delay(...)` is called **only** when `CreateQueuedRunResult.created` is `True`. Duplicate `409` paths never touch the Celery task.

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/constants.py` | Added `REPORT_RUN_ACTIVE_STATUSES` and `REPORT_RUN_TERMINAL_STATUSES` |
| `backend/operations/models.py` | Added partial unique constraint on active runs |
| `backend/operations/migrations/0003_unique_active_report_run_per_store.py` | Created — constraint migration |
| `backend/operations/services.py` | Added `create_queued_run_for_store`, `get_active_run_for_store`, `CreateQueuedRunResult` |
| `backend/operations/views.py` | Updated `ReportGenerateView` for 202/409 behavior |
| `backend/operations/tests/test_report_generate_api.py` | Extended — duplicate prevention API and service tests |
| `.cursor/rules/step-5.3-prevent-concurrent-report-runs.mdc` | Scope rule for this step |
| `docs/phases/step-5.3.md` | Created — this document |

---

## Tests added

In `backend/operations/tests/test_report_generate_api.py`:

**API tests (`ReportGenerateAPITests`):**

- First request creates a queued run (`202 Accepted`) and enqueues Celery
- Second request while `queued` returns `409` and does not enqueue
- Second request while `running` returns `409`
- Request after `completed` creates a new run
- Request after `failed` creates a new run
- Different stores under the same tenant can run independently
- Different tenants do not block each other

**Service / constraint tests (`ReportRunDuplicatePreventionServiceTests`):**

- Service creates first run
- Service returns existing active run without creating
- Simulated `IntegrityError` race returns existing run
- Database constraint blocks two active runs for same tenant/store
- Terminal runs (`completed`, `failed`) do not block a new active run

---

## Validation commands

Start the stack:

```bash
docker compose up --build
```

Check services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs backend
docker compose logs celery-worker
```

Apply migrations (if not auto-applied):

```bash
docker compose exec backend python manage.py migrate
```

Run tests:

```bash
docker compose exec backend python manage.py test operations.tests.test_report_generate_api
```

Or run the full backend test suite:

```bash
docker compose exec backend python manage.py test
```

If the project uses pytest:

```bash
docker compose exec backend pytest operations/tests/test_report_generate_api.py
```

---

## What is intentionally not implemented in this step

- **Step 5.4** — mock coordinator HTTP server and full integration test
- Scheduled daily reports (Celery beat cron)
- Phase 6 — agent scaffold, LangGraph, LLM abstraction, specialist agents
- `cancelled` status for `ReportRun` (not in current model)
- Frontend duplicate-handling UI (backend contract only)

---

## Next step

**Step 5.4 — Integration test with mock coordinator HTTP server**

Build a lightweight mock coordinator that returns predictable HTTP responses so the Celery task lifecycle can be exercised end-to-end in tests without real agent services.
