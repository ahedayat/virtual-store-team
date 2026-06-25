# Step 0.2 — Frontend Dockerfile & Next.js Shell

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2025-06-25  
**Status:** Implemented

---

## Scope

Step 0.2 delivers a **frontend container foundation only**:

- Minimal Next.js (App Router + TypeScript) shell under `frontend/`
- `Dockerfile`, `entrypoint.sh`, and dependency/config files
- Placeholder dashboard page identifying the app
- Development (`next dev`) and production (`next build` + `next start`) startup modes

**Out of scope for this step:** dashboard features, authentication, API clients, reports, actions, tenant UI, styling systems, business logic, Prestia-specific UI, docker-compose wiring, nginx, and backend changes.

---

## Files created/changed

| Path | Action |
|------|--------|
| `frontend/package.json` | Created — Next.js scripts and dependencies |
| `frontend/package-lock.json` | Created — npm lockfile |
| `frontend/tsconfig.json` | Created — TypeScript config |
| `frontend/next.config.mjs` | Created — minimal Next.js config |
| `frontend/next-env.d.ts` | Created — Next.js TypeScript references |
| `frontend/.eslintrc.json` | Created — ESLint config (`next/core-web-vitals`) |
| `frontend/.gitignore` | Created — standard Next.js ignores |
| `frontend/app/layout.tsx` | Created — root layout with metadata |
| `frontend/app/page.tsx` | Created — placeholder home page |
| `frontend/app/globals.css` | Created — minimal base styles |
| `frontend/Dockerfile` | Created — multi-stage Node 20 Alpine image |
| `frontend/entrypoint.sh` | Created — dev/prod start modes |
| `frontend/.dockerignore` | Created — exclude node_modules, .next, etc. |
| `docs/phases/step-0.2.md` | Created — this document |

---

## Implementation details

### Next.js project layout

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Package manager:** npm
- **Dev server:** binds `0.0.0.0:3000` via `npm run dev`
- **Production server:** `next build` at image build time; `next start` on `0.0.0.0:3000`

### Placeholder page

- **Route:** `/`
- **Content:** “Virtual Store Team Dashboard” heading and “Frontend is running” message
- No API calls, auth, or tenant-specific content

### Entrypoint (`frontend/entrypoint.sh`)

1. `set -eu` — exit on error
2. Start mode from first argument:
   - `dev` (default for development target) → `npm run dev`
   - `prod` or `start` → runs `npm run build` if `.next` is missing, then `npm run start`
   - any other value → `exec "$@"` for custom commands

### Dockerfile

- Base: `node:20-alpine`
- Multi-stage targets:
  - **`development`** — installs deps, no production build; `CMD ["dev"]`
  - **`production`** (default final stage) — `npm run build` at image build time; `CMD ["prod"]`
- `ENTRYPOINT ["/app/entrypoint.sh"]`
- `NEXT_TELEMETRY_DISABLED=1`
- `chmod +x` applied to `entrypoint.sh` at build time

---

## Frontend Docker build/run notes

### Build (production image — default)

```bash
docker build -t virtual-store-frontend:step-0.2 ./frontend
```

### Build (development image)

```bash
docker build --target development -t virtual-store-frontend:step-0.2-dev ./frontend
```

### Run (production server)

```bash
docker run --rm -p 3000:3000 virtual-store-frontend:step-0.2
```

### Run (development server with hot reload)

```bash
docker run --rm -p 3000:3000 virtual-store-frontend:step-0.2-dev
```

### Custom command

```bash
docker run --rm virtual-store-frontend:step-0.2 npm run type-check
```

### Host development (without Docker)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Verification commands

```bash
# 1. Install dependencies
cd frontend && npm install

# 2. Type-check
cd frontend && npm run type-check

# 3. Lint
cd frontend && npm run lint

# 4. Production build (host)
cd frontend && npm run build

# 5. Entrypoint shell syntax (host)
sh -n frontend/entrypoint.sh

# 6. Build Docker image (production)
docker build -t virtual-store-frontend:step-0.2 ./frontend

# 7. Start container and probe home page
docker run --rm -d --name vs-frontend-test -p 3000:3000 virtual-store-frontend:step-0.2
curl -s http://localhost:3000/ | head -20
docker stop vs-frontend-test

# 8. Development image smoke test
docker build --target development -t virtual-store-frontend:step-0.2-dev ./frontend
docker run --rm -d --name vs-frontend-dev -p 3001:3000 virtual-store-frontend:step-0.2-dev
curl -s http://localhost:3001/ | head -20
docker stop vs-frontend-dev
```

---

## Result of verification

| Check | Result |
|-------|--------|
| `npm install` | **Passed** — 331 packages installed; `package-lock.json` generated |
| `npm run type-check` | **Passed** — no TypeScript errors |
| `npm run lint` | **Passed** — no ESLint warnings or errors |
| `npm run build` | **Passed** — static `/` page built successfully |
| `sh -n frontend/entrypoint.sh` | **Passed** — no shell syntax errors |
| `docker build` | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |
| Container HTTP probe | **Pending** — requires Docker daemon running |

**Action for developer:** Start Docker Desktop (or the local Docker daemon), then run the Docker verification commands above. All should pass on a machine with Docker running.

---

## Decisions made

1. **Created minimal Next.js shell** — `frontend/` did not exist; scaffolded App Router + TypeScript with npm per project conventions.
2. **Multi-stage Dockerfile** — `development` and `production` targets keep dev images fast (no build step) while production images bake `next build` at image build time.
3. **Entrypoint modes via first arg** — Mirrors Step 0.1 backend pattern (`dev` / `prod`); custom commands supported via `exec "$@"`.
4. **Bind `0.0.0.0:3000`** — Required for container networking; configured in `package.json` scripts, not only in Docker.
5. **No `output: 'standalone'`** — Deferred to keep the Dockerfile simple; full `node_modules` + `.next` in the image is acceptable for this foundation step.
6. **Minimal ESLint config** — `.eslintrc.json` with `next/core-web-vitals` enables non-interactive `npm run lint`.

---

## What was intentionally not implemented

- Dashboard features, reports, actions, or history UI
- Authentication, session handling, or protected routes
- API client layer or `NEXT_PUBLIC_API_BASE_URL` wiring
- Tenant-specific or Prestia-specific UI or business rules
- Component library, design system, or substantial styling
- `docker-compose.yml` changes
- nginx reverse proxy
- Backend changes
- Health endpoint (can be added in a later step if required for compose healthchecks)

---

## Dependency on Step 0.1

Step 0.2 is **independent** of the backend container for build and run. The frontend image does not depend on the backend image or Django settings. Step 0.1 established the backend Docker pattern (entrypoint modes, multi-environment startup) that this step mirrors for consistency ahead of Step 0.4 compose wiring.

---

## Next step: Step 0.3 agent Dockerfiles

Create Dockerfiles (and minimal FastAPI shells if missing) for `coordinator-agent`, `sales-agent`, `content-agent`, and `support-agent` under `agents/`, still without full compose wiring unless already present.

---

*End of Step 0.2 implementation document.*
