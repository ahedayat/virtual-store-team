# Step 1.7 — Phase 1 Seed Prestia Baseline Alignment

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Clarify and verify the Phase 1 baseline responsibility of `seed_prestia`. For Phase 1, the command must guarantee only an idempotent `prestia` tenant and main store — not catalog, product, category, order, inventory, or message demo data.

This step does **not** close Phase 1. Subphases **1.8** (tenant scoping contract) and **1.9** (final verification) remain.

---

## Scope

- Inspect existing `seed_prestia` management command behavior
- Confirm Phase 1 tenant/store baseline is idempotent
- Document the boundary between Phase 1 baseline and later-phase catalog/demo seeding
- Add focused Phase 1.7 baseline tests (tenant/store only)
- Add a Phase 1.7 Cursor rule guardrail
- Verify migration check and relevant tests

**Out of scope:** Phase 1.8, Phase 1.9, Phase 2 auth, Store API changes, frontend, agents, removing later-phase seed behavior.

---

## Background / gap being closed

Phase 1 planning (`docs/phases/step-0.0.md`) requires:

> `seed_prestia` baseline: idempotent Prestia tenant and main store creation (catalog seeding deferred to later phases)

The command was extended in Phase 3+ to seed categories, products, orders, inventory, and messages. Without explicit Phase 1.7 alignment, it was unclear whether catalog/demo data was a Phase 1 requirement.

This step closes that ambiguity: **Phase 1 depends only on tenant/store baseline.** Later catalog/demo seed behavior remains in `seed_prestia` for convenience but is attributed to Phase 3+ and Phase 12.

---

## Phase 1 baseline definition

| Requirement | Phase 1? |
|-------------|----------|
| `Tenant(slug='prestia')` exists | Yes |
| Main `Store(slug='main')` for Prestia tenant exists | Yes |
| Idempotent on repeated runs (no duplicate tenant/store) | Yes |
| Categories, products, orders, inventory, messages | No (later phases) |

---

## `seed_prestia` behavior

**Command path:** `backend/tenants/management/commands/seed_prestia.py`

### Phase 1 baseline (required)

1. `Tenant.objects.get_or_create(slug='prestia', ...)` — name `"Prestia"`, settings `{"store_display_name": "Prestia"}`
2. `Store.objects.get_or_create(tenant=tenant, slug='main', ...)` — name `"Prestia Online Store"`, timezone `"America/New_York"`, currency `"USD"`

### Later-phase demo data (not Phase 1 requirements)

When catalog models are installed, the same command also seeds (idempotently):

- Categories and products (Phase 3.1)
- Orders and order items (Phase 3.2)
- Inventory levels (Phase 3.3)
- Customers, message threads, and messages (Phase 3.4)

This demo data is preserved; Phase 1.7 does not remove it. Phase 1 tests do not assert catalog counts.

---

## Idempotency guarantees

| Record | Natural key | Mechanism |
|--------|-------------|-----------|
| Tenant | `slug='prestia'` (globally unique) | `get_or_create` |
| Store | `(tenant, slug='main')` (unique per tenant) | `get_or_create` |
| Catalog/demo rows | Per-model natural keys (SKU, order_number, etc.) | `get_or_create` |

Repeated `python manage.py seed_prestia` runs do not create duplicate Prestia tenants or duplicate main Prestia stores.

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/phase-1-7-seed-prestia-baseline.mdc` | Verified (already present) |
| `backend/tenants/management/commands/seed_prestia.py` | Clarified Phase 1 baseline vs later-phase seeding in help text and comments |
| `backend/tenants/tests/test_seed_prestia_baseline.py` | Added Phase 1.7 baseline/idempotency tests |
| `docs/phases/step-1.7.md` | Created (this file) |

No migration changes. No changes to catalog seed logic, Store API, frontend, or agents.

---

## Tests added or verified

### Added — Phase 1.7 baseline (`tenants.tests.test_seed_prestia_baseline`)

| Test | Asserts |
|------|---------|
| `test_seed_prestia_creates_prestia_tenant_when_missing` | Creates `prestia` tenant with expected defaults |
| `test_seed_prestia_creates_main_prestia_store_when_missing` | Creates main store linked to Prestia tenant |
| `test_seed_prestia_does_not_create_duplicate_tenants` | Second run leaves tenant count at 1 |
| `test_seed_prestia_does_not_create_duplicate_main_stores` | Second run leaves main store count at 1 per tenant |
| `test_phase1_baseline_does_not_require_catalog_data` | Baseline satisfied via tenant/store only (no catalog imports) |

### Verified — existing later-phase seed tests (unchanged)

`catalog.tests.test_seed_prestia` continues to cover catalog/order/inventory/message idempotency for Phase 3+ acceptance. Those tests are **not** Phase 1 requirements.

---

## Verification commands

```bash
# Phase 1.7 baseline tests
docker compose run --rm --entrypoint "" backend python manage.py test tenants.tests.test_seed_prestia_baseline -v 2

# Related app tests
docker compose run --rm --entrypoint "" backend python manage.py test tenants stores accounts -v 2

# Migration drift check
docker compose run --rm --entrypoint "" backend python manage.py makemigrations --check --dry-run
```

---

## Verification results

Recorded after implementation run on 2026-06-26.

| Check | Result |
|-------|--------|
| `tenants.tests.test_seed_prestia_baseline` (5 tests) | **PASS** |
| `tenants`, `stores`, `accounts` (102 tests) | **PASS** |
| `makemigrations --check --dry-run` | **PASS** — `No changes detected` |

---

## Acceptance criteria checklist

- [x] `seed_prestia` guarantees a `prestia` tenant
- [x] `seed_prestia` guarantees a main Prestia store
- [x] Running `seed_prestia` repeatedly does not create duplicate tenant/store records
- [x] Tests prove idempotent tenant/store baseline
- [x] Later catalog/demo seed data is not treated as a Phase 1 requirement
- [x] `python manage.py makemigrations --check --dry-run` passes
- [x] `docs/phases/step-1.7.md` exists and documents the work
- [x] Working tree contains only Phase 1.7-related changes

---

## Non-goals

- Phase 1.8 tenant scoping contract finalization
- Phase 1.9 final Phase 1 verification and closure
- Phase 2 login/logout/JWT/service JWT
- Removing or rewriting later-phase catalog/demo seed behavior
- Store API endpoint changes from Phase 1.6
- Frontend or agent modifications

---

## Next step

**Phase 1.8 — Tenant Scoping Contract Finalization**

Finalize whether tenant-facing code must use explicit scoped accessors (`for_tenant`, `get_for_tenant`, `for_request`) vs automatic default-manager filtering, and document the accepted MVP contract.
