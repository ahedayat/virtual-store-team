# Step 4.7 — Dashboard Actions Read APIs

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Expose dashboard-facing read-only APIs so managers can list and inspect actions (including pending approvals) with filtering, safe payload summaries, and tenant/store isolation.

---

## Scope of implementation

- `GET /api/actions/` — paginated action list, newest first
- `GET /api/actions/{id}/` — action detail for approval dashboard
- `DashboardActionService` with filtering and safe `payload_summary`
- `ActionListQuerySerializer` for query validation
- Focused API tests in `operations.tests.test_dashboard_actions_api`

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/dashboard_service.py` | Updated — action list/detail serialization, filters, safe payload helper |
| `backend/operations/dashboard_serializers.py` | Updated — `ActionListQuerySerializer` |
| `backend/operations/views.py` | Updated — `ActionListView`, `ActionDetailView` |
| `backend/operations/urls.py` | Updated — action list/detail routes |
| `backend/operations/tests/test_dashboard_actions_api.py` | Created — Step 4.7 read API tests |
| `docs/phases/step-4.7.md` | Created — this document |

---

## Endpoints

### `GET /api/actions/`

**Filters:** `status`, `action_type`, `agent` (alias for `agent_name`), `requires_approval`, `from`, `to`  
**Pagination:** `limit`, `offset`

**Response fields per item:** `id`, `action_type`, `title`, `description`, `status`, `status_reason`, `priority`, `requires_approval`, `agent_name`, `report_run_id`, `store_id`, `created_at`, `updated_at`, `decided_by`, `decided_at`, `payload_summary`

### `GET /api/actions/{id}/`

Same shape as a list item for a single action.

---

## PII-safe payload summary

`payload_summary` includes only operational keys (e.g. `sku`, `product_id`, `thread_id`, `rationale`). Sensitive keys such as `email`, `phone`, `draft_text`, and `customer_phone` are excluded.

---

## Validation commands

```bash
cd backend
python manage.py test operations.tests.test_dashboard_actions_api.DashboardActionsAPITests -v 2
```

---

## Acceptance criteria

- [x] List and detail access for authenticated scoped users
- [x] Filter by `status` (including `pending_approval`) and `action_type`
- [x] Filter by agent and `requires_approval`
- [x] Tenant/store isolation
- [x] Unauthorized and service JWT rejected
- [x] Safe payload summaries (no raw PII)

---

## Next step

Step 4.8 — Manager Approve/Reject APIs
