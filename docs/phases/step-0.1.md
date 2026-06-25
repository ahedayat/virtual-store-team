# Step 0.1 — Backend Dockerfile & Entrypoint

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2025-06-25  
**Status:** Implemented

---

## Scope

Step 0.1 delivers a **backend container foundation only**:

- Minimal Django project shell under `backend/`
- `Dockerfile`, `entrypoint.sh`, and dependency files
- `/health/` JSON endpoint
- Development (`runserver`) and production (`gunicorn`) startup modes

**Out of scope for this step:** multi-tenancy, users, agents, reports, actions, Celery, Redis, frontend, nginx, docker-compose wiring, Postgres integration, and any Prestia-specific logic.

---

## Files created/changed

| Path | Action |
|------|--------|
| `backend/manage.py` | Created — Django CLI entry |
| `backend/config/` | Created — project settings, URLs, WSGI/ASGI |
| `backend/core/` | Created — minimal app with health endpoint |
| `backend/requirements.txt` | Created — Django + gunicorn |
| `backend/Dockerfile` | Created — Python 3.12-slim image |
| `backend/entrypoint.sh` | Created — migrate + configurable start command |
| `backend/.dockerignore` | Created — exclude caches, venv, sqlite, etc. |
| `docs/phases/step-0.1.md` | Created — this document |

---

## Implementation details

### Django project layout

- **Project package:** `config` (`DJANGO_SETTINGS_MODULE=config.settings`)
- **App:** `core` — hosts the health check only
- **Database:** SQLite (`backend/db.sqlite3`) for this step; no `psycopg` dependency yet
- **Settings:** `SECRET_KEY`, `DJANGO_DEBUG`, and `ALLOWED_HOSTS` read from environment variables with safe development defaults

### Health endpoint

- **URL:** `GET /health/`
- **Response:** `{"status": "ok"}` with `Content-Type: application/json`

### Entrypoint (`backend/entrypoint.sh`)

1. `set -eu` — exit on error
2. Optional database wait when `DATABASE_HOST` is set (uses `nc`; no-op for SQLite-only runs)
3. `python manage.py migrate --noinput`
4. Start mode from first argument:
   - `dev` (default) → `python manage.py runserver 0.0.0.0:8000`
   - `prod` or `gunicorn` → Gunicorn on `0.0.0.0:8000` (workers via `GUNICORN_WORKERS`, default `3`)
   - any other value → `exec "$@"` for custom commands

### Dockerfile

- Base: `python:3.12-slim`
- Installs `netcat-openbsd` for optional DB host checks
- `ENTRYPOINT ["/app/entrypoint.sh"]`, default `CMD ["dev"]`
- `chmod +x` applied to `entrypoint.sh` at build time

---

## Docker build/run notes

### Build

```bash
cd backend
docker build -t virtual-store-backend:step-0.1 .
```

### Run (development server)

```bash
docker run --rm -p 8000:8000 virtual-store-backend:step-0.1
```

### Run (Gunicorn / production mode)

```bash
docker run --rm -p 8000:8000 virtual-store-backend:step-0.1 prod
```

### Custom command

```bash
docker run --rm virtual-store-backend:step-0.1 python manage.py check
```

### Environment variables (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | insecure dev key | Django secret |
| `DJANGO_DEBUG` | `true` | Debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Host header allowlist |
| `DATABASE_HOST` | unset | If set, entrypoint waits for TCP port before migrate |
| `DATABASE_PORT` | `5432` | Port for database wait |
| `GUNICORN_WORKERS` | `3` | Gunicorn worker count in prod mode |

---

## Verification commands

```bash
# 1. Build image
cd backend && docker build -t virtual-store-backend:step-0.1 .

# 2. Django system check (inside container)
docker run --rm virtual-store-backend:step-0.1 python manage.py check

# 3. Start dev server and probe health
docker run --rm -d --name vs-backend-test -p 8000:8000 virtual-store-backend:step-0.1
curl -s http://localhost:8000/health/
docker stop vs-backend-test

# 4. Gunicorn mode smoke test
docker run --rm -d --name vs-backend-gunicorn -p 8001:8000 virtual-store-backend:step-0.1 prod
curl -s http://localhost:8001/health/
docker stop vs-backend-gunicorn

# 5. Entrypoint shell syntax (host)
sh -n backend/entrypoint.sh
```

---

## Result of verification

| Check | Result |
|-------|--------|
| `sh -n backend/entrypoint.sh` | **Passed** — no shell syntax errors |
| `entrypoint.sh` executable bit | **Passed** — `-rwxr-xr-x` on host; `chmod +x` in Dockerfile |
| `docker build` | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |
| `python manage.py check` (host venv) | **Not run** — local Python lacks SSL module for `pip install` |
| Container health probe | **Pending** — requires Docker daemon running |

**Action for developer:** Start Docker Desktop (or the local Docker daemon), then run the verification commands above. All should pass on a machine with Docker running.

---

## Decisions made

1. **SQLite for Step 0.1** — Keeps the step atomic without Postgres, compose, or `psycopg`. Settings are structured so `DATABASE_URL` / Postgres can be added in a later step.
2. **Project name `config`** — Neutral, common Django convention; avoids coupling to a tenant or product name.
3. **`core` app for health** — Single-purpose app; future platform code can live in separate apps per phase plan.
4. **Entrypoint modes via first arg** — Simple `dev` / `prod` switch without extra env parsing; custom commands still supported via `exec "$@"`.
5. **Optional `DATABASE_HOST` wait** — Forward-compatible for compose + Postgres in later steps; no-op when unset (current default).
6. **No `psycopg` in requirements** — Not required while SQLite is the only configured engine.

---

## What was intentionally not implemented

- Multi-tenant models, authentication, or user management
- Business domain models (products, orders, reports, actions)
- Celery, Redis, or async task wiring
- Postgres / `DATABASE_URL` parsing in settings
- Frontend, nginx, agent services
- `docker-compose.yml`
- Prestia-specific seeds, logic, or configuration
- Production hardening beyond basic Gunicorn binding (TLS, static file serving, etc.)

---

## Next step: Step 0.2 frontend Dockerfile

Create `frontend/Dockerfile` (and minimal Next.js shell if missing) for the dashboard container, still without full compose wiring unless already present.

---

*End of Step 0.1 implementation document.*
