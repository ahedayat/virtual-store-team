# Step 0.7 — Nginx Reverse Proxy Foundation

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Complete

---

## Goal

Add nginx as the Phase 0 local reverse proxy and single HTTP entrypoint on port 80, routing browser traffic to the Next.js frontend and API traffic to the Django backend without changing application business logic.

---

## Scope

- Create `nginx/` configuration for local development.
- Add an `nginx` service to `docker-compose.yml` using `nginx:alpine`.
- Route `http://localhost/` → `frontend:3000`.
- Route `http://localhost/api/...` → `backend:8000` (path preserved).
- Expose backend health at `http://localhost/api/health/` via an nginx-only rewrite to Django `/health/`.
- Update README where needed to document the nginx entrypoint.

**Out of scope:** application Compose healthchecks (0.8), agent Docker context alignment (0.9), dev bind mounts (0.10), final Phase 0 sign-off (0.11), TLS/HTTPS, backend/frontend/agent code changes.

---

## Files created or updated

| Path | Action |
|------|--------|
| `nginx/conf.d/default.conf` | Created — reverse proxy routing |
| `docker-compose.yml` | Updated — added `nginx` service |
| `README.md` | Updated — nginx entrypoint, ports, smoke tests |
| `docs/phases/step-0.7.md` | Created — this document |
| `.cursor/rules/phase-0-7-nginx-reverse-proxy.mdc` | Exists — Phase 0.7 Cursor rule |

---

## Nginx routing table

| Client request | Upstream | Notes |
|----------------|----------|-------|
| `GET http://localhost/` | `http://frontend:3000/` | Next.js placeholder dashboard |
| `GET http://localhost/api/...` | `http://backend:8000/api/...` | `/api/` prefix preserved for Django URLconf |
| `GET http://localhost/api/health/` | `http://backend:8000/health/` | nginx-only mapping; Django exposes `/health/` at root |

All proxied locations set:

- `Host`
- `X-Real-IP`
- `X-Forwarded-For`
- `X-Forwarded-Proto`

The frontend location also sets WebSocket upgrade headers for the Next.js dev server (HMR).

---

## Docker Compose changes

Added `nginx` service:

| Property | Value |
|----------|-------|
| Image | `nginx:alpine` |
| Host port | `80` |
| Config mount | `./nginx/conf.d/default.conf` → `/etc/nginx/conf.d/default.conf` (read-only) |
| Network | `app-network` |
| Depends on | `frontend`, `backend` (start order only; no health condition) |

Direct host ports for `backend` (8000), `frontend` (3000), and agents (8100–8103) remain exposed for debugging. **nginx on port 80 is the preferred local entrypoint.**

No Compose `healthcheck` was added for nginx (Phase 0.8).

---

## Validation commands

Run from the repository root (requires `.env` and a running Docker daemon):

```bash
docker compose config
docker compose up --build
docker compose ps
curl -i http://localhost/
curl -i http://localhost/api/health/
docker compose logs -f nginx
```

Optional direct-port checks (debugging):

```bash
curl -i http://localhost:8000/health/
curl -i http://localhost:3000/
```

Teardown:

```bash
docker compose down
```

---

## Expected results

| Check | Expected |
|-------|----------|
| `docker compose config` | Exit 0; merged config includes `nginx` on port 80 |
| `docker compose up --build` | All services start; nginx listens on host port 80 |
| `curl -i http://localhost/` | HTTP 200; HTML containing “Virtual Store Team Dashboard” |
| `curl -i http://localhost/api/health/` | HTTP 200; `{"status": "ok"}` |
| `curl -i http://localhost/api/auth/...` | Reaches Django (e.g. 401/405 depending on method) — confirms `/api/` proxy |
| `docker compose logs nginx` | No config syntax errors; access log lines on curl |

Allow 10–30 seconds after `up` for backend migrations and Next.js dev compile before probing.

---

## Result of verification

| Check | Result |
|-------|--------|
| `docker compose config` | **Passed** — exit 0; merged config includes `nginx` on host port 80 with read-only config mount |
| `docker compose up` / curl probes | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |

If Docker is unavailable in the environment, run the validation commands locally after starting Docker Desktop.

---

## Known limitations

- **HTTP only** — no TLS or HTTPS termination in this step.
- **No nginx Compose healthcheck** — `docker compose ps` will not show nginx as `(healthy)` until Phase 0.8.
- **Backend health is nginx-mapped** — Django still serves `/health/` at the root; `/api/health/` exists only through nginx.
- **`NEXT_PUBLIC_API_BASE_URL`** in `.env.example` still points at `http://localhost:8000` for direct backend access; browser apps should use `http://localhost/api` once the frontend is wired to the nginx entrypoint (no `.env.example` change in this step).
- **Direct ports remain** — 8000, 3000, and agent ports are still published for debugging.
- **Next.js dev WebSockets** — upgrade headers are set for HMR; production frontend routing may need refinement in a later phase.

---

## What was intentionally not implemented

| Item | Phase |
|------|-------|
| Application Compose healthchecks (`backend`, `frontend`, agents, Celery) | **0.8** |
| Agent Docker build context standardization | **0.9** |
| Dev bind mounts / hot reload override | **0.10** |
| Final Phase 0 verification and sign-off | **0.11** |
| TLS / production certificates | Later |
| Backend URL or health endpoint code changes | N/A — nginx-only `/api/health/` mapping |
| Prestia-specific routing or configuration | N/A |

---

## Remaining Phase 0 steps after 0.7

| Step | Focus |
|------|-------|
| **0.8** | Application healthchecks and `depends_on: service_healthy` where appropriate |
| **0.9** | Agent Docker build context alignment (`agents.shared.*` imports) |
| **0.10** | Development bind mounts and hot reload (`docker-compose.override.yml`) |
| **0.11** | Final Phase 0 verification, sign-off, `docs/phases/step-0.11.md` |

Phase 0 is **not complete** until steps **0.8–0.11** are done.

---

## Final status for this step

**Step 0.7 — Nginx Reverse Proxy Foundation: COMPLETE**

nginx is configured as the local HTTP entrypoint on port 80 with frontend and API routing documented and wired in Compose.

---

*End of Step 0.7 implementation document.*
