# Step 4.2 — ActionService Transition Methods

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Implement strict action lifecycle transition methods in the backend service layer so managers can approve or reject pending actions and approved actions can be queued for future execution — without performing side effects in this step.

---

## Summary of implemented changes

- Added `ActionTransitionError` for invalid or unauthorized lifecycle transitions
- Extended action/event constants and model choices for `approved`, `rejected`, `queued`, and user actors
- Implemented `ActionService.approve()`, `ActionService.reject()`, and `ActionService.queue_execution()`
- Centralized transition validation, row locking (`select_for_update()`), and transactional audit event creation
- Added focused unit tests for successful transitions, forbidden transitions, tenant isolation, and actor authorization
- Cursor scope rule already present at `.cursor/rules/step-4.2-action-transitions.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `backend/operations/constants.py` | Updated — added transition event types and user actor constant |
| `backend/operations/exceptions.py` | Updated — added `ActionTransitionError` |
| `backend/operations/models.py` | Updated — extended `ActionEventType` and `ActionEventActorType` choices |
| `backend/operations/services.py` | Updated — added approve/reject/queue_execution and shared transition helper |
| `backend/operations/tests/test_action_service.py` | Updated — added `ActionServiceTransitionTests` |
| `backend/operations/migrations/0002_action_event_transition_choices.py` | Created — extended ActionEvent choice fields |
| `.cursor/rules/step-4.2-action-transitions.mdc` | Already present — Step 4.2 scope rule |
| `docs/phases/step-4.2.md` | Created — this document |

---

## Transition methods added

```python
ActionService.approve(
    *,
    action: Action,
    actor: User,
    reason: str | None = None,
    metadata: dict | None = None,
) -> Action

ActionService.reject(
    *,
    action: Action,
    actor: User,
    reason: str | None = None,
    metadata: dict | None = None,
) -> Action

ActionService.queue_execution(
    *,
    action: Action,
    actor: User | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> Action
```

All three methods delegate to a shared `_transition_action()` helper that:

1. Locks the action row with `select_for_update()`
2. Validates the current status matches the expected source status
3. Updates action fields inside `transaction.atomic()`
4. Creates exactly one new `ActionEvent`

---

## Allowed transition table

| Method | From status | To status | Actor requirement |
|--------|-------------|-----------|-------------------|
| `approve()` | `pending_approval` | `approved` | Trusted human user (`UserRole.MANAGER` or `is_staff=True`) in same tenant |
| `reject()` | `pending_approval` | `rejected` | Trusted human user (`UserRole.MANAGER` or `is_staff=True`) in same tenant |
| `queue_execution()` | `approved` | `queued` | Optional human user (tenant-checked) or system actor when `actor=None` |

---

## Forbidden transitions

The service raises `ActionTransitionError` for invalid transitions, including:

| Attempt | Current status | Result |
|---------|----------------|--------|
| Approve | not `pending_approval` | Error |
| Reject | not `pending_approval` | Error |
| Queue | not `approved` | Error |
| Approve / reject / queue | `rejected` | Error (terminal) |
| Approve / reject / queue | `executed` | Error |
| Approve / reject / queue | `failed` | Error |
| Approve / reject | `queued` | Error |
| Queue | `queued` (already queued) | Error — not idempotent |
| Approve / reject | actor from another tenant | Error |
| Approve / reject | viewer role | Error |
| Approve / reject | non-`User` actor (e.g. service identity) | Error |

Auto-executable actions created as `queued` in Step 4.1 are not executed or re-queued in this step.

---

## Audit event behavior

Every successful transition creates exactly one `ActionEvent`:

| Field | Approve | Reject | Queue |
|-------|---------|--------|-------|
| `event_type` | `approved` | `rejected` | `queued` |
| `previous_status` | `pending_approval` | `pending_approval` | `approved` |
| `new_status` | `approved` | `rejected` | `queued` |
| `actor_type` | `user` | `user` | `user` or `system` |
| `actor_id` | manager user UUID | manager user UUID | user UUID or `"system"` |
| `reason` | provided reason or empty | provided reason or empty | provided reason or empty |
| `metadata` | optional caller metadata | optional caller metadata | optional caller metadata |

The action update and event insert happen in a single database transaction.

---

## Fields updated by each service method

### `approve()`

- `status` → `approved`
- `decided_by` → actor
- `decided_at` → current timestamp
- `status_reason` → set when `reason` is provided
- Creates one `ActionEvent`

### `reject()`

- `status` → `rejected` (terminal)
- `decided_by` → actor
- `decided_at` → current timestamp
- `status_reason` → set when `reason` is provided
- Creates one `ActionEvent`

### `queue_execution()`

- `status` → `queued`
- Does **not** set `executed_at`
- Does **not** set `execution_result`
- Does **not** call external APIs or Celery
- Creates one `ActionEvent`

---

## Actor authorization assumptions

- `approve()` and `reject()` require a Django `User` with `UserRole.MANAGER` or `is_staff=True`.
- The actor's `tenant_id` must match the action's tenant.
- `UserRole.VIEWER` cannot approve or reject.
- AI service identities (`AIServiceIdentity`) and other non-user actors cannot approve or reject.
- Store-level user scoping is not enforced beyond tenant match in this step; Step 4.3 API endpoints may add stricter store checks if needed.

---

## `queue_execution()` idempotency

Calling `queue_execution()` on an action that is already `queued` raises `ActionTransitionError`. This keeps the state machine strict and avoids silently masking invalid calls. Auto-queued actions from Step 4.1 remain in `queued` status until Phase 5 execution wiring.

---

## Tests added

`ActionServiceTransitionTests` in `backend/operations/tests/test_action_service.py` covers:

1. Approving `pending_approval` → `approved`
2. Rejecting `pending_approval` → `rejected`
3. Queueing `approved` → `queued`
4. Approve sets `decided_by` and `decided_at`
5. Reject sets `decided_by`, `decided_at`, and reason
6. Each successful transition creates exactly one new `ActionEvent`
7. Approving a non-`pending_approval` action fails
8. Rejecting a non-`pending_approval` action fails
9. Queueing a non-`approved` action fails
10. Rejected actions are terminal
11. Actor from another tenant cannot approve or reject
12. Service/agent identity cannot approve or reject
13. `queue_execution()` does not set `executed_at` or `execution_result`
14. Cannot approve/reject already `queued` actions
15. `queue_execution()` on already `queued` action raises error
16. Viewer role cannot approve or reject
17. Reject event records reason and metadata

---

## Validation commands

```bash
cd backend

# Run Step 4.2 transition tests
python manage.py test operations.tests.test_action_service.ActionServiceTransitionTests -v 2

# Run all action service tests (Step 4.1 + 4.2)
python manage.py test operations.tests.test_action_service -v 2

# Run full backend test suite
python manage.py test -v 1

# Migration check (no new migrations required for this step)
python manage.py makemigrations --check
```

---

## Intentionally not implemented in this step

- `POST /internal/ai/actions/`
- `POST /internal/ai/agent-outputs/`
- `POST /internal/ai/report-runs/{id}/complete/`
- `GET /api/history/`
- `POST /api/actions/{id}/approve/`
- `POST /api/actions/{id}/reject/`
- Celery `actions.execute`
- Real Instagram send/publish integration
- Any external API write
- Frontend action approval UI

---

## Notes for Step 4.3

- Internal AI POST endpoints should continue to call `ActionService.create_from_agent_payload()` with tenant/store from validated service JWT context.
- Dashboard approve/reject endpoints (later phase) should call `ActionService.approve()` and `ActionService.reject()` with the authenticated manager user as `actor`.
- After manager approval, a future endpoint or Celery hook can call `ActionService.queue_execution()` before dispatching execution in Phase 5.
- Map `ActionTransitionError` to `400 Bad Request` or `409 Conflict` in API views depending on whether the action state changed concurrently.
- Consider adding store-scoped actor validation when dashboard endpoints are implemented if managers should only act on their assigned store.
