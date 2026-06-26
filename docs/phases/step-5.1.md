# Step 5.1 — Celery & Redis Wiring in Docker Compose

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Configure Celery inside the Django backend with Redis as the broker and result backend, wire `celery-worker` and `celery-beat` services in Docker Compose, and document the environment variables needed to run async workers in the compose stack.

This step proves that Celery can start, connect to Redis, and discover tasks. It does **not** implement report generation or coordinator integration.

---

## What was changed

- Added standard Django + Celery app bootstrap in `backend/config/celery.py`.
- Imported the Celery app from `backend/config/__init__.py` so Django loads it on startup.
- Added `CELERY_*` settings in `backend/config/settings.py`, sourced from environment variables with Redis defaults suitable for Docker Compose.
- Added `celery` and `redis` Python dependencies.
- Added `celery-worker` and `celery-beat` services to `docker-compose.yml` using the same backend image and `.env` file.
- Added a minimal smoke task `core.debug_celery_connection` for optional worker verification.
- Documented required env vars in `.env.example`.
- Added Cursor scope rule at `.cursor/rules/step-5.1-celery-compose.mdc`.

---

## Files touched

| Path | Action |
|------|--------|
| `backend/config/celery.py` | Created — Celery app, settings namespace, autodiscover |
| `backend/config/__init__.py` | Updated — import `celery_app` |
| `backend/config/settings.py` | Updated — `REDIS_URL`, `CELERY_*` settings |
| `backend/core/tasks.py` | Created — `debug_celery_connection` smoke task |
| `backend/requirements.txt` | Updated — `celery`, `redis` |
| `docker-compose.yml` | Updated — `celery-worker`, `celery-beat` services |
| `.env.example` | Updated — Celery/Redis variables |
| `.cursor/rules/step-5.1-celery-compose.mdc` | Scope rule for this step |
| `docs/phases/step-5.1.md` | Created — this document |

---

## Environment variables added

| Variable | Example | Used by |
|----------|---------|---------|
| `REDIS_URL` | `redis://redis:6379/0` | Django settings default for Celery URLs |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery message broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | Celery task result store |

All three default to `redis://redis:6379/0` when unset, matching the Docker Compose Redis service DNS name.

Copy `.env.example` to `.env` before running compose if you do not already have a local `.env` file.

---

## Docker Compose services affected

| Service | Command | Depends on |
|---------|---------|------------|
| `redis` | `redis-server` (image default) | — |
| `backend` | Django dev server via entrypoint | `postgres`, `redis` |
| `celery-worker` | `celery -A config worker -l info` | `backend`, `postgres`, `redis` |
| `celery-beat` | `celery -A config beat -l info` | `backend`, `postgres`, `redis` |

`celery-worker` and `celery-beat` reuse the backend Dockerfile, `env_file: .env`, and the same `DATABASE_HOST` / `DATABASE_PORT` environment overrides as the Django backend.

---

## Celery configuration summary

- **Django settings module:** `config.settings` (same as `manage.py` and Gunicorn).
- **Celery app module:** `config.celery:app` (invoked as `celery -A config`).
- **Broker / result backend:** from `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.
- **Serialization:** JSON only (`CELERY_ACCEPT_CONTENT`, task/result serializers).
- **Timezone:** `CELERY_TIMEZONE` aligned with Django `TIME_ZONE` (`UTC`).
- **Task discovery:** `app.autodiscover_tasks()` across `INSTALLED_APPS`.

---

## How to validate worker connection to Redis

### 1. Start the stack

```bash
cp .env.example .env   # if you do not already have .env
docker compose up --build
```

### 2. Check service status

```bash
docker compose ps
```

Expect `redis`, `backend`, `celery-worker`, and `celery-beat` to be running.

### 3. Inspect worker logs

```bash
docker compose logs celery-worker
```

Look for lines similar to:

- `Connected to redis://redis:6379/0`
- `celery@... ready.`
- Registered task: `core.debug_celery_connection`

### 4. Inspect Redis logs (optional)

```bash
docker compose logs redis
```

### 5. Optional smoke task from Django shell

```bash
docker compose exec backend python manage.py shell
```

```python
from core.tasks import debug_celery_connection

result = debug_celery_connection.delay()
result.get(timeout=10)
```

Expected result:

```python
{'status': 'ok', 'message': 'Celery worker is connected.'}
```

### 6. Optional Celery inspect

```bash
docker compose exec celery-worker celery -A config inspect ping
```

---

## What is intentionally NOT implemented in this step

- `reports.generate_daily` Celery task and report workflow
- `POST /api/reports/generate/` enqueue endpoint
- Coordinator-agent HTTP calls
- ReportRun lifecycle updates from async tasks (`queued` → `running` → `completed`/`failed`)
- Duplicate concurrent ReportRun prevention per store
- `actions.execute` Celery task
- Celery beat maintenance schedules (stale run cleanup)
- Integration tests with a mock coordinator HTTP server
- Frontend report generation UX

---

## Next step: Step 5.2

Step 5.2 will implement the report generation task lifecycle:

- Create or update a `ReportRun` and transition status to `running`
- Call the coordinator-agent over HTTP
- Mark the run `completed` or `failed` based on coordinator response
- Wire `POST /api/reports/generate/` to enqueue the task

That work builds on the Celery/Redis foundation configured here.
