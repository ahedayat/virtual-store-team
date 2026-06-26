# Step 0.10 — Dev Bind Mounts & Hot Reload

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Complete

---

## Goal

Add development-only bind mounts and hot reload support so local source edits are reflected inside running containers without rebuilding images, while keeping dependency and build directories safe inside containers.

Phase 0.10 is **local-development-only**. It does not perform final Phase 0 sign-off, does not add new application features, and does not alter tenant, agent, LLM, Celery, or business workflows.

---

## Scope

- Create `docker-compose.override.yml` with dev bind mounts for `backend`, `frontend`, and all four agent services.
- Enable hot reload where the existing dev commands already support it (Django `runserver`, Next.js dev server, uvicorn `--reload`).
- Protect container-installed dependency and cache directories from host bind mounts.
- Update README with local development workflow notes.
- Create/update Phase 0.10 Cursor rule.

**Out of scope:** nginx routing changes (0.7), healthcheck redesign (0.8), agent Docker build context changes (0.9), final Phase 0 verification (0.11), new business logic, production deployment behavior, Celery worker/beat bind mounts.

---

## Files created or updated

| Path | Action |
|------|--------|
| `docker-compose.override.yml` | Created — dev bind mounts and uvicorn `--reload` overrides |
| `.cursor/rules/phase-0-10-dev-bind-mounts-hot-reload.mdc` | Updated — explicit Phase 0.10 scope and constraints |
| `README.md` | Updated — local development / hot reload section and Phase 0 status |
| `docs/phases/step-0.10.md` | Created — this document |

`docker-compose.yml` was not changed. No Dockerfile or entrypoint changes were required.

---

## Bind mounts added by service

| Service | Host path | Container path | Notes |
|---------|-----------|----------------|-------|
| `backend` | `./backend` | `/app` | Matches backend `WORKDIR`; pip packages remain in image site-packages |
| `frontend` | `./frontend` | `/app` | Matches frontend `WORKDIR` |
| `coordinator-agent` | `./agents` | `/app/agents` | Preserves Phase 0.9 `PYTHONPATH=/app` layout |
| `sales-agent` | `./agents` | `/app/agents` | Full `agents/` tree mounted for `agents.shared.*` imports |
| `content-agent` | `./agents` | `/app/agents` | Same mount strategy as other agents |
| `support-agent` | `./agents` | `/app/agents` | Same mount strategy as other agents |

Services **not** given dev bind mounts in this step: `postgres`, `redis`, `celery-worker`, `celery-beat`, `nginx`. Restart Celery services manually after backend code changes, or rebuild images when dependencies change.

---

## Hot reload behavior by service

| Service | Dev server | Reload mechanism | Override change |
|---------|------------|------------------|-----------------|
| `backend` | Django `runserver` (entrypoint `dev` mode) | Django autoreload on `.py` changes | Bind mount only |
| `frontend` | `npm run dev` / `next dev` | Next.js Fast Refresh / HMR | Bind mount only |
| `coordinator-agent` | uvicorn | `--reload` watches under `/app` (includes `/app/agents`) | Command override in override file |
| `sales-agent` | uvicorn | `--reload` | Command override |
| `content-agent` | uvicorn | `--reload` | Command override |
| `support-agent` | uvicorn | `--reload` | Command override |

Service ports unchanged: backend `8000`, frontend `3000`, agents `8100`–`8103`.

---

## Dependency directory protection strategy

| Protected path | Service | Mechanism |
|----------------|---------|-----------|
| `/app/node_modules` | `frontend` | Anonymous volume masks host (avoids empty/mismatched host `node_modules` clobbering image install) |
| `/app/.next` | `frontend` | Anonymous volume preserves container build cache / dev output |
| Python site-packages | `backend`, agents | Not under bind-mounted app paths; `pip install` during image build stays in image |
| `__pycache__`, `.pytest_cache` | all Python services | Host copies may appear under mounted source trees; listed in `.gitignore` where applicable — not mounted over site-packages |

When `package.json`, `requirements.txt`, or Dockerfiles change, rebuild affected images:

```bash
docker compose build backend frontend coordinator-agent sales-agent content-agent support-agent
docker compose up -d
```

To reset anonymous frontend volumes after dependency or Next.js cache issues:

```bash
docker compose down
docker volume prune   # review listed volumes before confirming
docker compose up --build
```

---

## Validation commands

```bash
docker compose config
docker compose up --build
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f coordinator-agent
docker compose logs -f sales-agent
docker compose logs -f content-agent
docker compose logs -f support-agent
```

### Optional manual hot reload checks

1. Edit a backend Python file (e.g. health view) and confirm Django logs a reload or the HTTP response changes.
2. Edit a frontend component and confirm the browser reflects the change via Next.js dev server.
3. Edit an agent module under `agents/` and confirm uvicorn logs `Reloading` for the affected agent.
4. Inside the frontend container, confirm `/app/node_modules` and `/app/.next` are not empty host bind mounts:

   ```bash
   docker compose exec frontend ls -la /app/node_modules | head
   docker compose exec frontend ls -la /app/.next 2>/dev/null || echo ".next may be created on first request"
   ```

5. Inside an agent container, confirm shared imports still work:

   ```bash
   docker compose exec coordinator-agent python -c "import agents.shared; import agents.coordinator; print('ok')"
   ```

---

## Validation results (this implementation run)

| Command | Result |
|---------|--------|
| `docker compose config` | **Passed** — override volumes and agent `--reload` commands merge correctly |
| `docker compose up --build` | **Not run** — Docker daemon unavailable in implementation environment |
| Hot reload manual checks | **Not run** — requires running stack locally |

Re-run `docker compose up --build` and manual reload checks when Docker is available.

---

## Expected results

After `docker compose up --build` with Docker running:

- `docker compose config` shows bind mounts for backend, frontend, and agents from `docker-compose.override.yml`.
- Backend serves on port 8000 with Django autoreload active.
- Frontend serves on port 3000 with Next.js dev server; `node_modules` and `.next` remain container-backed.
- All four agents listen on ports 8100–8103 with uvicorn reload enabled.
- Agent containers import `agents.shared.*` and their per-agent package without `ModuleNotFoundError`.
- `docker compose ps` healthchecks behave as in Phase 0.8 (allow startup time after reload).

---

## Known limitations

- **Celery worker/beat** do not bind-mount backend source; restart them after backend task code changes.
- **uvicorn `--reload`** is dev-only (override file); production-like `docker-compose.yml` commands stay without `--reload`.
- **Full `agents/` tree** is visible in each agent container via the mount; cross-agent package imports may work in dev but each production image still copies only shared + one agent package (Phase 0.9).
- **First frontend start** after volume reset may be slower while Next.js compiles into the protected `.next` volume.
- **Host OS file watching** on macOS/Windows bind mounts can add slight reload latency compared to Linux.

---

## What was intentionally not implemented

- Final Phase 0 verification checklist and sign-off (**Phase 0.11**)
- nginx routing or TLS changes
- New or redesigned application healthchecks
- Agent Docker build context changes beyond preserving Phase 0.9
- Celery worker/beat bind mounts or autoreload
- New backend, frontend, agent, tenant, auth, LLM, or business logic
- Prestia-specific configuration
- Production deployment or compose profiles for prod/staging

Phase 0.10 does **not** close Phase 0. Phase 0.11 remains required for final verification and `docs/phases/step-0.11.md`.

---

## Remaining Phase 0 steps after 0.10

| Step | Name | Status after 0.10 |
|------|------|-------------------|
| **0.11** | Final Phase 0 verification & sign-off | Required |

---

## Final status for this step

**Step 0.10 is complete** for dev bind mounts, hot reload overrides, documentation, and `docker compose config` validation.

**Phase 0 is not complete** until Step 0.11 is implemented and documented in `docs/phases/step-0.11.md`.
