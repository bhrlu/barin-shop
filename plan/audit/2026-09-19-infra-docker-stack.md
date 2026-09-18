# Audit — 2026-09-19 — infra docker compose stack

> ⚠️ **PARTIALLY SUPERSEDED (same day, later — Session 3).** This file describes the
> first cut of the stack, built around **hosted Supabase** and
> `initdb/01-auth-shim.sql`. A later unlogged change made the FastAPI service the
> sole backend: **`initdb/01-auth-shim.sql` no longer exists**, `02-public-schema.sql`
> was rewritten around a real `public.users` table (RLS dropped), and the compose
> `db-init` job now runs `seed_auth` + `seed_coupons` with `JWT_SECRET`/`MINIO_*`
> instead of `SUPABASE_*`. Read the file below as history, not current state — current
> state: [2026-09-19-sole-backend-no-supabase.md](2026-09-19-sole-backend-no-supabase.md).
> `infra/README.md` still matches this old text and needs a rewrite (task B3.3).

## Task

User request (ad-hoc): "create docker compose file for backend and
vogue-vintage-vibes project and each dependency they need, for example postgres
or minio …, in an `infra` folder like Claude Code version."

User chose the **lightweight stack** option (asked via multiple-choice):
Postgres + MinIO + backend + frontend. Supabase stays **hosted** — consistent
with the Session-1 decision in `plan/session-log.md`.

## What was done

Created a new `infra/` folder with a full local dev stack:

- **`infra/docker-compose.yml`** — services:
  - `postgres` (postgres:16-alpine, port 5432, healthcheck, `pgdata` volume)
  - `minio` (S3 API :9000, console :9001, healthcheck, `miniodata` volume)
  - `minio-init` (one-shot: creates public-read `product-images` bucket)
  - `db-init` (one-shot: runs `startup_ddl()` + seeds SANDE10/WELCOME500)
  - `backend` (FastAPI, :8000, `/health` healthcheck, hot-reload bind mount)
  - `frontend` (Bun + Vite dev server, :5173, hot-reload bind mount,
    `node_modules` preserved via named volume)
- **`infra/backend.Dockerfile`** — python:3.12-slim, deps layer cached,
  uvicorn `--reload` dev default, curl for healthcheck.
- **`infra/frontend.Dockerfile`** — oven/bun:1; injects a temporary
  `overrides` entry pinning `@lovable.dev/vite-tanstack-config@2.13.1` to the
  public npm registry (the repo's bun.lock tarball URL returns 403 outside
  Lovable's sandbox — verified). Repo's package.json / bun.lock untouched.
- **`infra/.env.example`** — Supabase (hosted) values, Zarinpal, Postgres,
  MinIO, ports/URLs, shipping rules.
- **`infra/initdb/01-auth-shim.sql`** — local `auth` schema (minimal
  `auth.users` + `auth.uid()` stub) and Supabase role names so the real
  migrations apply unchanged; creates the RLS `storage.objects` mirror table.
- **`infra/initdb/02-public-schema.sql`** — verbatim mirror of the 4 Supabase
  migrations (profiles, user_roles, products, addresses, favorites, orders,
  order_items, payments, refund_requests, policies, triggers, function
  hardening, storage policies) + the 20-product seed insert.
- **`infra/README.md`** — service map, quick start, gotchas (first-run-only
  initdb, hot reload, simulation-mode payments, local-vs-hosted auth caveat).

## Files changed

- `infra/docker-compose.yml` (new)
- `infra/backend.Dockerfile` (new)
- `infra/frontend.Dockerfile` (new)
- `infra/.env.example` (new)
- `infra/initdb/01-auth-shim.sql` (new)
- `infra/initdb/02-public-schema.sql` (new)
- `infra/README.md` (new)
- `plan/session-log.md` (session entry appended)
- (this audit file)

No changes to `backend/` or `vogue-vintage-vibes/` code.

## How to verify

```bash
# 1. validate compose file
docker compose -f infra/docker-compose.yml --env-file infra/.env.example config --quiet

# 2. full stack (after cp infra/.env.example infra/.env and filling SUPABASE_*)
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build
#    → http://localhost:5173 (store) · http://localhost:8000/docs (API)
#    → http://localhost:9001 (MinIO console)

# 3. what was actually run during this task:
#    - compose config --quiet                → COMPOSE OK
#    - initdb SQL applied to a scratch postgres:16 → all DDL + INSERT 0 20 OK
#    - backend pip install -e ".[dev]" + pytest → 19 passed
```

## What is NOT done / open

- Full `docker compose up --build` end-to-end run was **not** executed (would
  build the Bun image and pull ~1GB of images; user can run it). Compose file
  validated with `config`, SQL verified on a scratch Postgres, backend tests
  pass.
- `VITE_BACKEND_URL` is injected but no frontend code consumes it yet — that
  is task **F1.1** (`src/lib/backend.ts`) in `frontend-tasks.md`.
- Frontend Supabase-backed features (login, product browsing) still hit the
  hosted project; local Postgres users/roles are separate (documented).
- No production-grade compose (no TLS, no gunicorn/uvicorn workers, no
  `nitro build` frontend image); this is a dev stack by design.
