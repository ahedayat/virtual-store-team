# Step 1.5 — Accounts Migration Drift Closure

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Close the migration drift for `accounts.User` and its custom `accounts.managers.UserManager` so that `python manage.py makemigrations --check --dry-run` passes with no pending `accounts` migrations.

This step does **not** implement Phase 1.6 (tenant-scoped store API acceptance or HTTP-level cross-tenant isolation tests).

---

## Scope

- Inspect existing `accounts` model, manager, and migration state
- Confirm migration drift via `makemigrations --check --dry-run`
- Generate and commit the missing `accounts` migration using Django's migration tooling
- Re-run migration check and relevant app tests
- Document the work in this file

---

## What was wrong

Phase 1 completion review found that while `AUTH_USER_MODEL = "accounts.User"` and the custom user model/manager existed in code, Django still reported a pending migration:

```
Migrations for 'accounts':
  accounts/migrations/0002_alter_user_managers.py
    ~ Change managers on user
```

The model code and migration history were out of sync for the `User` model's manager.

---

## Root cause

`accounts/migrations/0001_initial.py` recorded the default Django auth manager in the migration state:

```python
managers=[
    ('objects', django.contrib.auth.models.UserManager()),
],
```

However, `backend/accounts/models.py` assigns the custom manager:

```python
objects = UserManager()
```

where `UserManager` lives in `backend/accounts/managers.py` and subclasses `BaseUserManager` with email-based `create_user` / `create_superuser` helpers.

The initial migration was created before the migration state reflected this custom manager (or was generated without Django detecting the manager change). Django therefore expected an `AlterModelManagers` migration to reconcile the recorded manager with the model definition.

---

## Files changed

| Path | Action |
|------|--------|
| `backend/accounts/migrations/0002_alter_user_managers.py` | Created — `AlterModelManagers` to clear the incorrect `django.contrib.auth.models.UserManager` entry from migration state |
| `docs/phases/step-1.5.md` | Created — this document |

No changes were required to `backend/accounts/models.py`, `backend/accounts/managers.py`, or `backend/config/settings.py`.

---

## Implementation details

Django's `makemigrations accounts` generated:

```python
migrations.AlterModelManagers(
    name='user',
    managers=[],
)
```

This removes the stale `django.contrib.auth.models.UserManager` reference from the migration graph. Django does not serialize `accounts.managers.UserManager` into migration state for this alteration; the runtime manager remains defined on the model class (`objects = UserManager()`). After applying `0002`, `makemigrations --check --dry-run` reports no further drift.

`AUTH_USER_MODEL = "accounts.User"` in `backend/config/settings.py` is unchanged and remains valid.

---

## Verification commands

**Run via Docker** (project convention):

```bash
docker compose run --rm --entrypoint "" backend python manage.py makemigrations --check --dry-run
docker compose run --rm --entrypoint "" backend python manage.py migrate accounts
docker compose run --rm --entrypoint "" backend python manage.py test accounts tenants stores
```

**Run locally** (from `backend/`):

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate accounts
python manage.py test accounts tenants stores
```

---

## Verification results

| Check | Result |
|-------|--------|
| `makemigrations --check --dry-run` (before fix) | Exit code 1 — pending `accounts/migrations/0002_alter_user_managers.py` |
| `makemigrations accounts` | Created `0002_alter_user_managers.py` |
| `makemigrations --check --dry-run` (after fix) | Exit code 0 — `No changes detected` |
| `migrate accounts` | Applied `accounts.0002_alter_user_managers` successfully |
| `test accounts tenants stores` | 91 tests — **OK** |

---

## Acceptance criteria checklist

- [x] `python manage.py makemigrations --check --dry-run` passes
- [x] No pending migration is reported for `accounts`
- [x] `AUTH_USER_MODEL = "accounts.User"` remains valid
- [x] Custom `accounts.managers.UserManager` is the runtime manager for `User`
- [x] Migration state no longer records the incorrect `django.contrib.auth.models.UserManager`
- [x] Relevant `accounts`, `tenants`, and `stores` tests pass
- [x] `docs/phases/step-1.5.md` documents the work
- [x] Scope limited to accounts migration drift closure (no Phase 1.6 work)

---

## Non-goals

- Phase 1.6 — tenant-scoped store read API and HTTP-level cross-tenant isolation tests
- Changes to `seed_prestia`
- Tenant middleware or tenant-scoped manager changes
- Authentication, store API, frontend, or agent changes
- Rewriting `0001_initial.py` (historical migration left intact; drift closed with additive `0002`)

---

## Next step

**Phase 1.6 — Tenant-Scoped Store API Acceptance**

Add or complete a minimal tenant-scoped store read API path and prove via HTTP-level tests that a user from one tenant cannot read another tenant's store by direct ID.
