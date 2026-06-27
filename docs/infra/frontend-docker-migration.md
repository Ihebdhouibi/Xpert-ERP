# Plan: containerize the frontend (Docker)

**Status:** PLANNED (not yet implemented)
**Recorded:** 2026-06-27

## Context

Everything in `infra/docker-compose.yml` is containerized **except the
frontend**: `db`, `redis`, `mailpit`, `minio`, `api` (backend, built from
`infra/Dockerfile.backend`) and `backup` all run as containers. The frontend
currently runs as the Vite dev server (`npm run dev`) on the host.

The deployment target is a single cost-optimized Orange Flexible Engine server
(see `infra/RAPPORT_OPTIMISATION_SERVEUR.fr.md` and
`infra/cost-optimization-log.md`), where the backend was already tuned hard for
low RAM.

## Key distinction

The backend is a long-running process — a container is its natural unit. The
frontend is a **static SPA**: `vite build` produces static files (`dist/`).
At runtime there is no "frontend process", just files a web server serves.

So "dockerize the frontend" means a **multi-stage image**:

1. **Build stage** (Node): `npm ci && npm run build` → `dist/`.
2. **Runtime stage** (`nginx:alpine`): serve `dist/` as static files.

The Vite dev server and its `/api` proxy are **dev-only** and are not used in
production.

## Decision

**Adopt it**, as a multi-stage `node → nginx` image, and make that nginx
container the **single public entrypoint / reverse proxy** for the stack:

- serve the SPA at `/`
- reverse-proxy `/api` → `api:8000` (same-origin → no CORS; replaces the
  dev-only Vite proxy)
- handle SPA history-API fallback (so deep links like `/tablet` work)
- gzip/brotli + long cache headers; the PWA service worker keeps working

**Hard rule: build the image in CI, not on the Orange server.** `npm ci` +
`vite build` is CPU/RAM-heavy and would fight the server's tight memory budget.
The running nginx container itself is negligible (a few MB).

## Pros

- Full parity: `docker compose up` brings up the entire stack; no Node
  toolchain to install/version-match on the server.
- Reproducible builds (pinned Node version) — no local-machine drift.
- Single public entrypoint + same-origin API (kills CORS, centralizes routing).
- Proper static serving (SPA fallback, compression, caching) for free.
- Versioned artifact + easy rollback, like the backend image.

## Cons / caveats

- Build is heavy (mitigated by building in CI).
- One more image + an `nginx.conf` to maintain.
- For a pure static SPA the container adds little *runtime* value vs. serving
  `dist/` from a host nginx — the value is parity + the reverse-proxy role.

## Lighter alternative (not chosen)

Serve `dist/` from FastAPI via `StaticFiles`: fewer moving parts, but loses the
clean proxy separation and puts static-serving load on the API worker.

## Implementation checklist (when picked up)

- [ ] `infra/Dockerfile.frontend` — multi-stage (`node:20` build → `nginx:alpine`).
- [ ] `infra/nginx.conf` — SPA fallback + `/api` → `api:8000` proxy + gzip + cache headers.
- [ ] `frontend` service in `infra/docker-compose.yml` (consider a `frontend-dev`
      profile that still runs the Vite dev server with HMR for local work).
- [ ] Point the SPA at same-origin `/api`; wire `VITE_API_BASE_URL` accordingly.
- [ ] CI job to build (and push) the frontend image so the server only pulls.
- [ ] Update deployment docs.
