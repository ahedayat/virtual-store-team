# Step 5.5 — Implement `actions.execute` Celery Task

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Implement the canonical `actions.execute` Celery task so queued actions can be processed asynchronously using the existing `Action` model, `ActionService` lifecycle, and audit events — without performing real external side effects in MVP.

---

## Scope of this step

- `ActionService.execute_stub()` — service-layer stub execution (`queued` → `executing` → `executed`)
- `actions.execute` Celery task in `operations/tasks.py`
- Action event types for `executing` and `executed`
- Focused unit tests for execution paths and task registration
- Environment/documentation only as needed (no new required env vars)

**Not in scope:** Real Instagram publish/send, price changes, inventory writes, dashboard enqueue API, or Phase 6+ agent logic.

---

## Canonical model reuse

The project already has a full `Action` model (`operations/models.py`) with:

| Field | Use in 5.5 |
|-------|------------|
| `status` | Only `queued` actions are executable |
| `executed_at` | Set on successful stub execution |
| `execution_result` | JSON stub outcome persisted |
| `requires_approval` / approval flow | Enforced upstream; task rejects `pending_approval` and `approved` |

Execution reuses `ActionService` transition patterns and creates `ActionEvent` audit rows — no parallel action model was introduced.

---

## Task behavior (`actions.execute`)

1. Load `Action` by UUID `action_id`.
2. If missing/invalid ID → log error, return `{"status": "skipped", "reason": "action_not_found"}`.
3. Call `ActionService.execute_stub(action=...)`.
4. Outcomes:

| Outcome | Task result | DB effect |
|---------|-------------|-----------|
| `executed` | `status=executed` + `execution_result` | `queued` → `executing` → `executed` |
| `already_executed` | `status=skipped`, `reason=already_executed` | None (idempotent) |
| `not_executable` | `status=skipped`, `reason=not_executable` | None (`pending_approval`, `approved`, etc.) |
| `terminal_skip` | `status=skipped`, `reason=terminal_skip` | None (`rejected`, `failed`, `cancelled`) |
| `already_executing` | `status=skipped`, `reason=already_executing` | None |

Stub `execution_result` example:

```json
{
  "outcome": "stubbed",
  "action_type": "sales.restock",
  "message": "MVP stub execution completed without external side effects."
}
```

Structured logs include `action_id`, `tenant_id`, `store_id`, `action_type`, and `execution_outcome` — never raw payloads or PII.

---

## MVP limitations (intentional)

- No real external integrations (Instagram, ERP, etc.).
- Task does not auto-enqueue from approve/queue APIs — callers enqueue explicitly in later phases.
- `already_executing` is a safe skip (no crash recovery re-drive in MVP).
- Persistence is **not** deferred — the canonical `Action` model and `ActionService` already exist from Phase 4.

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/constants.py` | Added `ACTION_EVENT_TYPE_EXECUTING`, `ACTION_EVENT_TYPE_EXECUTED` |
| `backend/operations/models.py` | Extended `ActionEventType` choices |
| `backend/operations/migrations/0004_action_event_execution_choices.py` | Migration for new event types |
| `backend/operations/services.py` | Added `ActionService.execute_stub()` |
| `backend/operations/tasks.py` | Added `actions.execute` task |
| `backend/operations/tests/test_execute_action_task.py` | Created — task tests |
| `docs/phases/step-5.5.md` | Created — this document |

---

## Tests added

`operations.tests.test_execute_action_task`:

- Successful execution of a `queued` action
- Idempotent skip for already `executed` actions
- Non-executable `pending_approval` and `approved` actions
- Missing/invalid action identifier
- Celery task name registration (`actions.execute`)

---

## Verification commands

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test operations.tests.test_execute_action_task
docker compose exec celery-worker celery -A config inspect registered | grep actions.execute
```

---

## Next step

**Step 5.6** — `maintenance.cleanup_stale_report_runs` and celery-beat schedule.
