# Step 0.8 — Application Healthchecks

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Complete

---

## Goal

Add Docker Compose healthchecks for application services and update `depends_on` conditions only where they improve startup reliability without creating fragile coupling.

---

## Scope

- Add Compose `healthcheck` directives for `backend`, `frontend`, four agent services, `celery-worker`, and `nginx`.
- Evaluate `celery-beat` and document why no healthcheck was added.
- Upgrade selected `depends_on` entries to `condition: service_healthy` where appropriate.
- Update README healthcheck documentation.
- Create Phase 0.8 Cursor rule.

**Out of scope:** nginx routing changes (0.7), agent Docker build context alignment (0.9), dev bind mounts (0.10), final Phase 0 sign-off (0.11), application code or Dockerfile changes.

---

## Files created or updated

| Path | Action |
|------|--------|
| `docker-compose.yml` | Updated — application healthchecks and `depends_on` conditions |
| `README.md` | Updated — healthcheck behavior, `docker compose ps`, Phase 0.8 status |
| `docs/phases/step-0.8.md` | Created — this document |
| `.cursor/rules/phase-0-8-application-healthchecks.mdc` | Exists — Phase 0.8 Cursor rule |

---

## Healthchecks added by service

| Service | Endpoint or check command | Expected healthy condition | Notes / limitations |
|---------|----------------------------|----------------------------|---------------------|
| `backend` | `python -c` → `GET http://localhost:8000/health/` | HTTP 200 from Django `/health/` | `start_period: 60s` allows migrations on first boot |
| `frontend` | `node -e` → `fetch('http://localhost:3000/')` | HTTP 200 from Next.js root | `start_period: 60s` allows dev server compile |
| `coordinator-agent` | `python -c` → `GET http://localhost:8100/health` | HTTP 200 JSON `{"status":"ok",...}` | May stay unhealthy if Phase 0.9 import errors prevent startup |
| `sales-agent` | `python -c` → `GET http://localhost:8101/health` | HTTP 200 JSON | Independent of backend; no `depends_on` added |
| `content-agent` | `python -c` → `GET http://localhost:8102/health` | HTTP 200 JSON | May stay unhealthy if Phase 0.9 import errors prevent startup |
| `support-agent` | `python -c` → `GET http://localhost:8103/health` | HTTP 200 JSON | Independent of backend; no `depends_on` added |
| `celery-worker` | `celery -A config inspect ping -d worker@celery-worker` | Worker responds with `pong` | Stable nodename `-n worker@celery-worker` added to worker command |
| `celery-beat` | *(none)* | — | See [Services without healthcheck](#services-intentionally-left-without-healthcheck) |
| `nginx` | `wget --spider` to `http://127.0.0.1/` | HTTP 200 from local nginx | Verifies nginx serves `/` (proxied frontend) |

**Unchanged infrastructure healthchecks:** `postgres` (`pg_isready`), `redis` (`redis-cli ping`) — added in Phase 0.4.

---

## Services intentionally left without healthcheck

### `celery-beat`

No reliable Celery-native healthcheck exists for the beat scheduler:

- `celery inspect ping` targets workers, not beat.
- Process-level checks (`pgrep`, PID files) only confirm a process exists, not that the scheduler is connected to Redis or writing schedules correctly.
- A misleading `healthy` status would be worse than no healthcheck for a maintenance-only MVP scheduler.

`celery-beat` still starts after `backend`, `postgres`, and `redis` are healthy. Verify manually with `docker compose logs -f celery-beat`.

---

## `depends_on` changes and rationale

| Service | Before | After | Rationale |
|---------|--------|-------|-----------|
| `backend` | `postgres`, `redis` → `service_healthy` | *(unchanged)* | Already correct — backend needs DB and broker ready |
| `celery-worker` | `backend` → `service_started` | `backend` → `service_healthy` | Worker needs Django migrations and settings loaded before Celery app boots reliably |
| `celery-beat` | `backend` → `service_started` | `backend` → `service_healthy` | Same as worker — beat shares Django/Celery config |
| `frontend` | `backend` (start order only) | `backend` → `service_healthy` | Frontend placeholder does not strictly need API, but waiting for backend avoids racing migrations during stack bring-up |
| `nginx` | `frontend`, `backend` (start order only) | both → `service_healthy` | Reverse proxy should start only after upstream HTTP endpoints respond |
| Agent services | no `depends_on` | *(unchanged)* | Agents expose standalone `/health` stubs; no startup dependency on backend required in Phase 0 |

---

## Validation commands

Run from the repository root (requires `.env` and a running Docker daemon):

```bash
docker compose config
docker compose up --build
docker compose ps
docker inspect --format='{{json .State.Health}}' virtual_store_team-backend-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-frontend-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-coordinator-agent-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-sales-agent-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-content-agent-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-support-agent-1
docker inspect --format='{{json .State.Health}}' virtual_store_team-celery-worker-1
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f coordinator-agent
docker compose logs -f sales-agent
docker compose logs -f content-agent
docker compose logs -f support-agent
docker compose logs -f celery-worker
docker compose logs -f celery-beat
```

Replace container names with output from `docker compose ps` if project directory name differs.

Host smoke tests (after services are healthy):

```bash
curl -s http://localhost:8000/health/
curl -s http://localhost:3000/ | head -5
curl -s http://localhost:8100/health
curl -s http://localhost/
curl -s http://localhost/api/health/
```

Teardown:

```bash
docker compose down
```

---

## Expected results

| Check | Expected |
|-------|----------|
| `docker compose config` | Exit 0; all `healthcheck` blocks present for application services |
| `docker compose up --build` | Stack starts; allow 60–90s for first-boot migrations and Next.js compile |
| `docker compose ps` | `backend`, `frontend`, `postgres`, `redis`, `celery-worker`, `nginx`, and agents that start successfully show `(healthy)` |
| `docker inspect ...State.Health` | `Status` transitions to `healthy` after `start_period` |
| `celery-worker` health | `celery inspect ping -d worker@celery-worker` succeeds inside container |
| `celery-beat` | Running (`Up`) but no `(healthy)` badge — intentional |
| Agent health curls | `{"status":"ok",...}` for agents that start without import errors |

---

## Result of verification

| Check | Result |
|-------|--------|
| `docker compose config` | **Passed** — exit 0; merged config includes all application healthchecks and updated `depends_on` conditions |
| `docker compose up` / `docker compose ps` | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |

If Docker is unavailable, run the validation commands locally after starting Docker Desktop.

---

## Known limitations

- **Backend `start_period` is 60s** — Django runs migrations in the entrypoint; aggressive intervals would mark the service unhealthy during normal first boot.
- **Frontend `start_period` is 60s** — Next.js dev server compile can delay the first successful HTTP response.
- **Agent import errors (Phase 0.9 blocker)** — `coordinator-agent` and `content-agent` may remain `unhealthy` or `restarting` until Docker build contexts are aligned in Phase 0.9. Healthchecks are wired; they cannot fix import failures.
- **`celery-beat` has no healthcheck** — no reliable Celery-native probe; use logs for verification.
- **nginx healthcheck uses `wget`** — checks local HTTP on port 80, not TLS. If `wget` is removed from a future `nginx:alpine` tag, the check may need adjustment.
- **Agents have no `depends_on: backend`** — intentional to avoid blocking unrelated services; coordinator HTTP calls to Django are not required for `/health` in Phase 0.

---

## What was intentionally not implemented

| Item | Phase |
|------|-------|
| Agent Docker build context standardization | **0.9** |
| Development bind mounts / hot reload | **0.10** |
| Final Phase 0 verification and sign-off | **0.11** |
| New application health endpoints | N/A — existing `/health/` and `/health` used |
| `celery-beat` healthcheck | Deferred — no reliable probe |
| Prestia-specific health behavior | N/A |

---

## Remaining Phase 0 steps after 0.8

| Step | Focus |
|------|-------|
| **0.9** | Agent Docker build context alignment (`agents.shared.*` imports) |
| **0.10** | Development bind mounts and hot reload (`docker-compose.override.yml`) |
| **0.11** | Final Phase 0 verification, sign-off, `docs/phases/step-0.11.md` |

Phase 0 is **not complete** until steps **0.9–0.11** are done.

---

## Final status for this step

**Step 0.8 — Application Healthchecks: COMPLETE**

Docker Compose healthchecks are configured for application services, `depends_on` conditions are tightened where appropriate, and documentation is updated. Phase 0 overall remains open pending steps 0.9–0.11.

---

*End of Step 0.8 implementation document.*
