# Step 5.6 — Stale Report Cleanup and Celery Beat Schedule

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Implement periodic maintenance that marks stale active `ReportRun` records as `failed`, and register the job in `CELERY_BEAT_SCHEDULE` so `celery-beat` has a real scheduled task.

---

## Scope of this step

- `ReportRunService.cleanup_stale_active_runs()`
- `maintenance.cleanup_stale_report_runs` Celery task
- Django settings: stale timeout, beat interval, `CELERY_BEAT_SCHEDULE`
- `.env.example` documentation for new variables
- Focused tests and beat-schedule verification

**Not in scope:** Additional beat jobs, scheduled daily reports, or Phase 6+ features.

---

## Stale run definition

| Category | Statuses | Cleanup behavior |
|----------|----------|------------------|
| Active | `queued`, `running` | Mark `failed` when `updated_at` older than timeout |
| Terminal | `completed`, `failed` | Never modified |

Staleness uses `updated_at` (aligned with status transition timestamps). Default timeout: **600 seconds** (10 minutes), matching Step 0.0 §13.4.

Failure message (persisted on `ReportRun.error_message`):

```
Report run marked failed by stale-run cleanup after exceeding the configured timeout (600s).
```

`ReportRunService.mark_failed()` provides idempotent terminal protection — repeated beat runs do not corrupt already-failed runs.

---

## Configuration

| Setting / env var | Default | Purpose |
|-------------------|---------|---------|
| `REPORT_RUN_STALE_TIMEOUT_SECONDS` | `600` | Age threshold for active runs |
| `CELERY_STALE_REPORT_CLEANUP_INTERVAL_SECONDS` | `300` | Beat schedule interval (5 minutes) |

Defined in `backend/config/settings.py`:

```python
CELERY_BEAT_SCHEDULE = {
    "maintenance-cleanup-stale-report-runs": {
        "task": "maintenance.cleanup_stale_report_runs",
        "schedule": timedelta(seconds=CELERY_STALE_REPORT_CLEANUP_INTERVAL_SECONDS),
    },
}
```

Only this maintenance job was added — no unrelated beat entries.

---

## Task behavior

`maintenance.cleanup_stale_report_runs`:

1. Calls `ReportRunService.cleanup_stale_active_runs()`.
2. Returns structured result:

```json
{
  "marked_failed_count": 1,
  "marked_failed_ids": ["<uuid>"],
  "stale_timeout_seconds": 600
}
```

3. Logs `marked_failed_count` and `stale_timeout_seconds` (no PII).

---

## Edge cases

| Case | Behavior |
|------|----------|
| Fresh `queued`/`running` run | Unchanged |
| Stale `queued` or `running` | Marked `failed` with cleanup message |
| Stale `completed`/`failed` | Unchanged; error message preserved |
| Already `failed` stale run | `mark_failed` no-op; count stays 0 |
| Concurrent beat executions | Safe/idempotent via terminal checks |
| Custom timeout in tests | `override_settings(REPORT_RUN_STALE_TIMEOUT_SECONDS=...)` |

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/services.py` | Added `ReportRunService.cleanup_stale_active_runs()` |
| `backend/operations/tasks.py` | Added `maintenance.cleanup_stale_report_runs` task |
| `backend/config/settings.py` | Stale timeout, beat interval, `CELERY_BEAT_SCHEDULE` |
| `.env.example` | Documented new env vars |
| `backend/operations/tests/test_cleanup_stale_report_runs.py` | Created — cleanup and schedule tests |
| `docs/phases/step-5.6.md` | Created — this document |

---

## Tests added

`operations.tests.test_cleanup_stale_report_runs`:

- Stale `queued` and `running` runs marked `failed`
- Fresh active run not modified
- Terminal runs not modified (error message preserved)
- Idempotent skip for already-failed stale runs
- Service returns useful count and timeout metadata
- `CELERY_BEAT_SCHEDULE` contains `maintenance.cleanup_stale_report_runs`
- Celery task name registration

---

## Verification commands

```bash
docker compose up --build
docker compose exec backend python manage.py test operations.tests.test_cleanup_stale_report_runs
docker compose exec celery-beat celery -A config inspect scheduled
docker compose exec celery-worker celery -A config inspect registered | grep maintenance.cleanup_stale_report_runs
```

---

## Phase 5 completion

With Steps 5.1–5.6 implemented, Phase 5 — **Celery & Async Wiring** is complete:

| Step | Deliverable | Status |
|------|-------------|--------|
| 5.1 | Celery + Redis wiring in compose | Done |
| 5.2 | `reports.generate_daily` lifecycle + coordinator HTTP | Done |
| 5.3 | Duplicate concurrent run prevention | Done |
| 5.4 | Mock coordinator integration tests | Done |
| 5.5 | `actions.execute` stub task | Done |
| 5.6 | Stale report cleanup + celery-beat schedule | Done |

---

## Next phase

**Phase 6: Agent Scaffold & LLM Abstraction**
