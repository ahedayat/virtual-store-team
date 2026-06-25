# Step 4.1 — ActionService.create_from_agent_payload()

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Implement the backend service logic that converts a validated agent action payload into a persisted `Action` record with the correct initial lifecycle status and an initial audit `ActionEvent`. This method is designed for reuse by internal AI endpoints in Step 4.3.

---

## Summary of implemented changes

- Added new Django app `operations` for Phase 4 workflow models
- Defined minimal Phase 4 models: `ReportRun`, `DailyReport`, `AgentOutput`, `Action`, `ActionEvent`
- Implemented `ActionService.create_from_agent_payload()` with payload validation, default action policy, tenant/store scoping, and transactional audit event creation
- Registered Phase 4 models in Django admin
- Added focused unit tests for action creation, validation, scoping, and default policy behavior
- Cursor scope rule already present at `.cursor/rules/step-4.1-action-service.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `backend/operations/__init__.py` | Created |
| `backend/operations/apps.py` | Created |
| `backend/operations/constants.py` | Created — action types, statuses, event types, agent names |
| `backend/operations/exceptions.py` | Created — `ActionPayloadValidationError`, `ActionScopeError` |
| `backend/operations/models.py` | Created — Phase 4 models |
| `backend/operations/services.py` | Created — `ActionService` |
| `backend/operations/admin.py` | Created — admin registration |
| `backend/operations/migrations/0001_initial.py` | Created |
| `backend/operations/tests/test_action_service.py` | Created — Step 4.1 tests |
| `backend/config/settings.py` | Updated — added `operations` to `INSTALLED_APPS` |
| `.cursor/rules/step-4.1-action-service.mdc` | Already present — Step 4.1 scope rule |
| `docs/phases/step-4.1.md` | Created — this document |

---

## Models and fields added

### `ReportRun`

Minimal report orchestration record for FK validation and future Phase 4/5 work.

- `tenant`, `store`, `status` (`queued`, `running`, `completed`, `failed`)
- `error_message`, `created_at`, `updated_at`

### `DailyReport`

Placeholder for final report content (not written in this step).

- `tenant`, `store`, `report_run` (OneToOne), `content` (JSON), `generated_at`, timestamps

### `AgentOutput`

Placeholder for per-agent structured output (not written in this step).

- `tenant`, `store`, optional `report_run`, `agent_name`, `output` (JSON), `created_at`

### `Action`

Primary model for Step 4.1.

- `tenant`, `store`, optional `report_run`, optional `source_agent_output`
- `agent_name`, `action_type`, `title`, `description`, `payload` (JSON)
- `priority` (1–5), `requires_approval`, `status`, `status_reason`
- Approval/execution fields reserved for later steps: `decided_by`, `decided_at`, `executed_at`, `execution_result`
- `created_at`, `updated_at`

### `ActionEvent`

Generic audit trail for lifecycle transitions.

- `action`, `event_type`, `previous_status`, `new_status`, `reason`
- `actor_type` (`agent`, `system`), `actor_id`, `metadata`, `created_at`

All tenant-owned models inherit `TenantScopedModel` and enforce tenant/store consistency in `clean()`.

---

## ActionService.create_from_agent_payload() behavior

```python
ActionService.create_from_agent_payload(
    *,
    tenant,
    store,
    agent_name: str,
    payload: dict,
    report_run=None,
    source_agent_output=None,
) -> Action
```

### Trusted context

- `tenant` and `store` must come from trusted server-side context (e.g. service JWT resolution or Celery task scope).
- `tenant_id` and `store_id` in the agent payload are ignored and never applied.
- If `report_run` or `source_agent_output` are provided, they must belong to the same tenant and store or `ActionScopeError` is raised.

### Validation

The service validates:

| Field | Rule |
|-------|------|
| `action_type` | Required; must be one of the supported MVP types |
| `title` | Required non-empty string |
| `description` | Required non-empty string |
| `priority` | Integer in range 1–5 (booleans rejected) |
| `payload` | JSON object (defaults to `{}`) |
| `requires_approval` | Optional boolean |
| `agent_name` | Must be in `ALLOWED_AI_SERVICES` (`coordinator-agent`, `sales-agent`, `content-agent`, `support-agent`) |

Validation failures raise `ActionPayloadValidationError`. Scope failures raise `ActionScopeError`.

### Transactional creation

Within a single database transaction the service:

1. Creates the `Action` with resolved status and `status_reason`
2. Creates exactly one initial `ActionEvent` with `event_type=created`

---

## Supported action payload format

```json
{
  "action_type": "sales.restock",
  "title": "Restock: Leather Tote Model A",
  "description": "Only 2 units left; sold 14 in last 7 days.",
  "priority": 1,
  "requires_approval": true,
  "low_risk": false,
  "payload": {
    "product_id": "uuid",
    "sku": "BAG-001",
    "current_stock": 2,
    "suggested_order_qty": 20
  }
}
```

### Supported action types

| Type | Default policy |
|------|----------------|
| `sales.restock` | Requires approval |
| `sales.discount` | Requires approval |
| `sales.follow_up` | Requires approval |
| `content.instagram_draft` | Requires approval |
| `content.product_description` | Requires approval |
| `support.reply_draft` | Requires approval unless low-risk |
| `support.escalate` | Requires approval |

Payload keys such as `tenant_id` and `store_id` are ignored.

---

## Initial status decision rules

| Condition | Initial `status` |
|-----------|------------------|
| `requires_approval=True` (explicit or default policy) | `pending_approval` |
| Auto-executable by policy | `queued` |

Policy resolution order:

1. If `requires_approval` is explicitly provided:
   - Use the explicit value
   - For `support.reply_draft` with `requires_approval=false`, auto-execution is allowed only when `low_risk=true` (top-level or inside nested `payload`); otherwise approval is still required
2. If not explicit:
   - `support.reply_draft` with `low_risk=true` → auto-executable (`queued`)
   - All other MVP types → approval required (`pending_approval`)

Queued actions are **not executed** in this step.

---

## Action event creation behavior

Each created action produces one `ActionEvent`:

| Field | Value on create |
|-------|-----------------|
| `event_type` | `created` |
| `previous_status` | empty string |
| `new_status` | `pending_approval` or `queued` |
| `reason` | Human-readable explanation of the policy decision |
| `actor_type` | `agent` |
| `actor_id` | Proposing `agent_name` |
| `metadata` | `action_type`, `requires_approval`, `policy_source` |

The event model is generic so Step 4.2 can reuse it for approve/reject/execution transitions.

---

## Tests added

`backend/operations/tests/test_action_service.py` covers:

1. Approval-required action → `pending_approval`
2. Auto-executable action → `queued`
3. Exactly one initial `ActionEvent` per action
4. Invalid `action_type` rejected
5. Missing required fields rejected
6. Invalid `priority` rejected
7. Payload `tenant_id`/`store_id` cannot override trusted context
8. Mismatched `report_run` tenant/store rejected
9. Mismatched `source_agent_output` tenant/store rejected
10. Default policy for all MVP action types
11. Low-risk `support.reply_draft` → `queued`
12. Non-low-risk `support.reply_draft` with `requires_approval=false` stays `pending_approval`
13. Matching `report_run` accepted

---

## Validation commands

```bash
cd backend

# Create/apply migrations
python manage.py makemigrations operations
python manage.py migrate --noinput

# Run Step 4.1 tests
python manage.py test operations.tests.test_action_service -v 2

# Run full backend test suite
python manage.py test -v 1
```

---

## Intentionally not implemented in this step

- `ActionService.approve()`, `.reject()`, `.queue_execution()`
- `POST /internal/ai/actions/`
- `POST /internal/ai/agent-outputs/`
- `POST /internal/ai/report-runs/{id}/complete/`
- `GET /api/history/`
- Manager approve/reject dashboard endpoints
- Celery action execution tasks
- Real external side effects (Instagram publish/send, price changes)
- Frontend UI

---

## Notes for Step 4.2

- Reuse `ActionEvent` for approve/reject transitions with new `event_type` values and `actor_type=user` for manager decisions
- Implement `ActionService.approve()` and `ActionService.reject()` against existing status fields
- `queue_execution()` should transition approved or auto-queued actions toward execution without performing side effects yet (or delegate to a stub Celery task in Phase 5)
- Internal AI POST endpoints (Step 4.3) should call `ActionService.create_from_agent_payload()` with tenant/store from the validated service JWT, not from the request body
- Consider extending `ActionEventType` choices for `approved`, `rejected`, `queued`, `executing`, `executed`, `failed`
