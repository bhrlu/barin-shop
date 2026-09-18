# Audit — 2026-09-19 — sole backend (no Supabase)

## Task

Ad-hoc work found in the working tree after Session 2 (files last touched 01:05–01:30,
never logged): turn the FastAPI service from a **sidecar that fills Supabase gaps** into
the store's **sole backend** — its own users + JWT auth, Postgres as the only data store,
MinIO instead of Supabase Storage, full product/order/admin API — and give the frontend a
typed API client.

**Honest scope note:** this audit was written *after the fact*, from the code, by the
session that added git. It exists so Rules 1 and 3 hold and the state is reviewable.
Intent below is inferred from code/comments, not from the original work.

## What was done

### Backend — became the sole service

- **Own auth, no Supabase:**
  - `app/security.py` — bcrypt password hashing (passlib) + HS256 JWT encode/decode.
  - `app/auth.py` — `AuthUser` / `AdminUser` / `DbSession` dependencies built on the own JWT.
  - `app/seed_auth.py` — bootstraps admin + demo customer from `ADMIN_EMAIL`/`ADMIN_PASSWORD`.
  - `app/services/roles.py` — role lookup from `public.user_roles`.
  - `app/config.py` — Supabase settings **removed**; now `DATABASE_URL`, `JWT_SECRET`,
    MinIO (`MINIO_*`), Zarinpal, URLs, shipping rules, bootstrap admin. Docstring states
    "There is no Supabase anymore."
- **New routers:** `auth` (login/signup/me), `products` (public list/detail, admin CRUD,
  soft-delete when a product has been ordered), `orders` (list/detail/patch/cancel/
  payment-complete/payment-session/refunds), `addresses`, `favorites`, `admin`
  (orders/payments/refunds/stats/users), `storage` (MinIO presigned sign + upload-url).
- **Kept from Session 1:** `health`, `search`, `stock`, `coupons`, `checkout`, `payments`.
- `app/main.py` — v0.2.0, 13 routers, CORS, Zarinpal `Status=NOK` middleware.
- `pyproject.toml` — added `passlib[bcrypt]` and `minio`.

Surface after the change: **40 operations across 34 paths** (was ~11 routes).

### Infra — local stack follows the new architecture

- `infra/initdb/01-auth-shim.sql` — **deleted** (nothing to shim: no Supabase `auth` schema).
- `infra/initdb/02-public-schema.sql` — rewritten: `public.users` is now a real table with
  `password_hash`; every FK that pointed at `auth.users` points at `public.users`; RLS
  policies/grants gone (authorization moved into the API).
- `infra/docker-compose.yml` — "no Supabase" stack: `db-init` runs
  `python -m app.seed_auth && python -m app.seed_coupons`; backend gets `JWT_SECRET` +
  `MINIO_*` + `ADMIN_*`; frontend gets `VITE_API_URL` / `VITE_MINIO_URL`.
- `infra/.env.example` — rewritten: `JWT_SECRET`, MinIO, ports/URLs. No `SUPABASE_*`.

### Frontend — client added, **not wired**

- `vogue-vintage-vibes/src/lib/api.ts` (new, 314 lines) — typed fetch client for the
  FastAPI backend; token in `localStorage` under `sande.access_token`; `ApiError`;
  base URL from `VITE_API_URL` with `VITE_BACKEND_URL` SSR fallback.
- **Nothing imports it yet.** All 24 other Supabase-using files are untouched, so the
  store still runs on Supabase. The header comment ("Replaces `@/integrations/supabase/*`")
  describes the intention, not the current state.

### Verified during this audit (not during the original work)

```bash
cd backend
.venv/bin/pip install -e ".[dev]"   # venv was stale: passlib + minio were missing
.venv/bin/python -m pytest -q       # 19 passed
.venv/bin/ruff check .              # All checks passed (2 lint errors fixed, see below)
DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db" JWT_SECRET="x" \
  .venv/bin/python -c "from app.main import app; print(len(app.openapi()['paths']))"  # → 34

docker compose -f infra/docker-compose.yml --env-file infra/.env.example config --quiet  # → 0
```

Two pre-existing ruff errors in `tests/test_pricing_and_coupons.py` were fixed so the
"ruff clean" claim is true again: an unsorted import block (auto-fixed) and one E501.

## Files changed

Backend (`backend/`):

- `app/config.py`, `app/security.py`, `app/auth.py`, `app/seed_auth.py`, `app/schemas.py`,
  `app/main.py`, `app/services/roles.py`
- `app/routers/auth.py`, `products.py`, `orders.py`, `addresses.py`, `favorites.py`,
  `admin.py`, `storage.py` (all new/rewritten)
- `pyproject.toml`, `.env.example`
- `tests/test_pricing_and_coupons.py` (lint fixes only, from this audit)

Infra (`infra/`):

- `initdb/01-auth-shim.sql` (deleted)
- `initdb/02-public-schema.sql`, `docker-compose.yml`, `.env.example`

Frontend (`vogue-vintage-vibes/`):

- `src/lib/api.ts` (new; unused)

Docs (`plan/`): this file + Session 3 in `session-log.md`.

## How to verify

```bash
# 1. backend unit tests + lint
cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check .

# 2. API surface
DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db" JWT_SECRET="x" \
  .venv/bin/python -c "from app.main import app; print(len(app.openapi()['paths']), 'paths')"

# 3. full stack (needs Docker; not run in this audit)
cp infra/.env.example infra/.env        # fill JWT_SECRET
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build
#    → http://localhost:8000/docs          API (40 operations)
#    → http://localhost:5173               store (still Supabase-backed)
#    → http://localhost:9001               MinIO console
#    → login: admin@sande.local / admin1234 (from db-init)
```

## What is NOT done / open

- **Bug — `DATABASE_URL` scheme (FIXED).** `backend/.env.example` and the compose
  default used `postgresql://…`, but the async engine needs `postgresql+asyncpg://…`;
  the plain form fails with `ModuleNotFoundError: psycopg2`. Fixed in the follow-up
  commit `fix(config): use the async driver in DATABASE_URL examples`.
- **Frontend migration is 0% wired.** `src/lib/api.ts` has no importer; login, catalog,
  cart, orders, favorites, admin all still call Supabase. `F1.2`–`F1.7` remain open.
- **End-to-end run not executed.** No live Postgres/MinIO, no login → order → payment
  walk-through, no backend integration tests (still only the 19 pure-logic unit tests).
  The new routers (`auth`, `products`, `orders`, `addresses`, `favorites`, `admin`,
  `storage`) have **no test coverage at all**.
- **`backend/README.md` is stale** — still documents Supabase JWT verification, the old
  route table, and no MinIO. Needs a rewrite.
- **`infra/README.md` is stale** — documents the deleted `01-auth-shim.sql`, "Supabase
  stays hosted (by design)", and `SUPABASE_*` env vars that no longer exist.
- **`backend/app/db.py` docstrings/comments are stale** — still say "connects directly to
  the Supabase Postgres database" and "tables the Supabase schema does not have yet".
- **`frontend-tasks.md` F1.1** describes `src/lib/backend.ts`; the real file is
  `src/lib/api.ts`. Task text should be corrected.
- Frontend typecheck/lint was **not** run (`node_modules` is absent outside Docker), so
  `api.ts` is not verified to compile.
