# Step 4.8 — Manager Approve/Reject APIs

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Wire existing `ActionService.approve()` and `ActionService.reject()` to manager-facing HTTP endpoints with session auth, tenant/store scoping, and audit trail preservation.

---

## Scope of implementation

- `POST /api/actions/{id}/approve/` — optional `reason` in body
- `POST /api/actions/{id}/reject/` — required non-empty `reason`
- Thin views delegating all business logic to `ActionService`
- Manager-only access (viewers receive `403`)
- Focused API tests in `operations.tests.test_dashboard_actions_api.ActionDecisionAPITests`

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/dashboard_serializers.py` | Updated — approve/reject request serializers |
| `backend/operations/views.py` | Updated — `ActionApproveView`, `ActionRejectView` |
| `backend/operations/urls.py` | Updated — approve/reject routes |
| `backend/operations/tests/test_dashboard_actions_api.py` | Created — Step 4.8 decision API tests |
| `docs/phases/step-4.8.md` | Created — this document |

---

## Endpoints

### `POST /api/actions/{id}/approve/`

**Body (optional):** `{ "reason": "..." }`  
**Success:** `200` with updated action representation  
**Errors:** `403` non-manager, `404` cross-scope, `400` invalid transition

### `POST /api/actions/{id}/reject/`

**Body (required):** `{ "reason": "non-empty string" }`  
**Success:** `200` with updated action representation  
**Errors:** `400` missing/blank reason or invalid transition

---

## Design notes

- Views validate request-level concerns (auth, role, scope, reason presence) only
- State machine and `ActionEvent` creation remain in `ActionService`
- No duplicate transition logic in views

---

## Validation commands

```bash
cd backend
python manage.py test operations.tests.test_dashboard_actions_api.ActionDecisionAPITests -v 2
```

---

## Acceptance criteria

- [x] Manager can approve pending action
- [x] Manager can reject with reason
- [x] Reject without reason fails
- [x] Invalid transitions fail
- [x] Viewers cannot approve/reject
- [x] Tenant/store isolation
- [x] `ActionEvent` audit created via service layer
- [x] Response returns updated action shape

---

## Next step

Step 4.9 — Phase 4 Alignment and Verification
