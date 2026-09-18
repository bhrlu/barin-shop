# Session Log

## Session 1 — 2026-09-19

**Scope chosen by user:** Python backend as sibling folder `backend/`, lean MVP
(core + highest-value Part-7 items), direct Postgres access (SQLAlchemy + asyncpg),
Supabase JWT verification. Later: create `plan/` folder with task lists, session
log, and the audit-after-every-task rule.

### ✅ What was done

1. **Read & analyzed** `FEATURES.md` (all 7 parts) and all 4 Supabase migrations
   to learn the exact schema (products, orders, order_items, payments,
   refund_requests, profiles, user_roles, storage policies) and conventions.
2. **Asked the user 4 scoping questions** (location, scope, DB access, auth) and
   built accordingly.
3. **Scaffolded `backend/`** as a sibling of `vogue-vintage-vibes/`:
   `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, FastAPI app.
4. **Implemented the 4 chosen MVP features:**
   - Real coupon system (new `coupons` + `coupon_redemptions` tables, validate +
     admin CRUD endpoints, usage caps, seed `SANDE10` + `WELCOME500`)
   - Zarinpal payment gateway (request/verify/callback, simulation mode without
     merchant id, manual verify endpoint; reuses `SND-…` refs and existing
     status strings)
   - Transactional stock decrement (FOR UPDATE locks, guarded decrement,
     server-side prices, single transaction checkout)
   - Product search (ranked ILIKE search, pagination)
5. **Auth**: Supabase JWT verification (HS256, aud=authenticated) + role
   resolution from `user_roles` with admin guard for coupon CRUD.
6. **Quality**: 19 unit tests (all pass), ruff clean, OpenAPI smoke test
   (11 routes, unauth `/checkout` → 401).
7. **Created `plan/` folder** per user request: `README.md`, `RULES.md`
   (audit-after-every-task rule), `backend-tasks.md`, `frontend-tasks.md`,
   `session-log.md` (this file), and `audit/` with the first audit file.

### ❌ What was NOT done (explicitly out of scope this session)

- No frontend changes at all — `vogue-vintage-vibes/` untouched; cart still has
  hardcoded `SANDE10`; payment page still uses the simulator.
- No notifications (SMS/email), reports/Excel, PDF invoices, recommendations,
  webhooks/background jobs (B2.x backlog).
- No DB integration tests against a live Postgres (only unit tests + smoke test).
- No new SQL migration files written into `vogue-vintage-vibes/supabase/` — the
  coupon tables are created idempotently by the backend at startup instead.
- Nothing committed to git; no servers started; no real credentials used.

### Decisions

- Coupon tables live in the same Supabase Postgres DB, created idempotently by
  the backend on startup (documented; can be moved to a proper migration later).
- Payment callback is unauthenticated (gateway-called) — it uses the DB session
  dependency directly; all other endpoints require the Supabase JWT.
- Status strings and money rules were copied verbatim from the existing code to
  avoid breaking the running store (see `plan/RULES.md` Rule 4).

## Session 2 — 2026-09-19

**Scope chosen by user:** ad-hoc task — create a `docker compose` setup in an
`infra/` folder for both projects with their dependencies (postgres, minio, …).
Via multiple-choice, user picked the **lightweight stack**: Postgres + MinIO +
backend + frontend containers, with Supabase remaining **hosted** (no
self-hosted Supabase services).

### ✅ What was done

1. Created `infra/` with `docker-compose.yml`, `backend.Dockerfile`,
   `frontend.Dockerfile`, `.env.example`, `README.md`.
2. Postgres service mirrors the 4 Supabase migrations locally via
   `initdb/01-auth-shim.sql` (auth schema shim + roles) and
   `initdb/02-public-schema.sql` (full schema + 20-product seed), so the
   backend's models match table-for-table.
3. MinIO + `minio-init` one-shot (public-read `product-images` bucket);
   `db-init` one-shot (coupon DDL + seed SANDE10/WELCOME500).
4. Frontend image runs Bun + `vite dev` with hot-reload bind mounts; works
   around the Lovable-sandbox-only `@lovable.dev/vite-tanstack-config` tarball
   (403 verified) via a temporary npm `overrides` pin to 2.13.1 — repo files
   untouched.
5. Verified: compose `config --quiet` OK; initdb SQL applied cleanly on a
   scratch postgres:16 (INSERT 0 20); backend `pip install -e .[dev]` + pytest
   → 19 passed.
6. Audit file: `plan/audit/2026-09-19-infra-docker-stack.md`.

### ❌ What was NOT done

- No full `docker compose up --build` end-to-end run (image builds left to
  the user; compose + SQL + backend tests verified separately).
- No frontend code changes (`VITE_BACKEND_URL` consumed only from F1.1 on).
- No production compose variant (TLS, workers, nitro build).
- Nothing committed to git.

### Decisions

- Lightweight stack per user choice; hosted Supabase stays the source for
  auth/data/storage — the local Postgres is the **backend's** database.
- Local schema is a verbatim mirror of the Supabase migrations (plus an auth
  shim) instead of a reduced subset, so backend models and any future local
  RLS work behave identically.
- Lovable tarball handled inside the Dockerfile only — repo package.json and
  bun.lock remain pristine.

## Session 3 — 2026-09-19 (⚠️ backfilled — this work was never logged)

**Scope:** unknown / no entry was written. The changes below were made between
01:05 and 01:30, i.e. *after* the Session 2 entry (00:54), and were discovered in
the working tree during Session 4. This section is reconstructed from the code.

### ✅ What was done

1. **The FastAPI backend became the store's sole backend — Supabase is gone.**
   The Session-1 model ("sidecar that verifies Supabase JWTs") was replaced by own
   auth: `security.py` (bcrypt + HS256), `auth.py` (`AuthUser`/`AdminUser`/`DbSession`),
   `seed_auth.py` (bootstrap admin), `services/roles.py`, and a `config.py` with
   `JWT_SECRET` instead of `SUPABASE_JWT_SECRET`.
2. **Full CRUD/domain API added:** `auth`, `products`, `orders`, `addresses`,
   `favorites`, `admin` (orders/payments/refunds/stats/users), `storage` (MinIO
   presigned URLs), alongside the Session-1 `health`/`search`/`stock`/`coupons`/
   `checkout`/`payments`. Result: **40 operations across 34 paths**.
3. **Infra moved to the new architecture:** `initdb/01-auth-shim.sql` **deleted**,
   `02-public-schema.sql` rewritten around a real `public.users` table (own
   `password_hash`, FKs re-pointed, RLS policies dropped — authorization lives in the
   API now), compose `db-init` now runs `seed_auth` + `seed_coupons`, frontend service
   gets `VITE_API_URL`/`VITE_MINIO_URL`.
4. **Frontend client added but not wired:** `vogue-vintage-vibes/src/lib/api.ts`
   (314 lines, typed fetch client, token in localStorage under `sande.access_token`).
   **No file imports it yet** — the store still runs on Supabase.
5. **Audit backfilled:** `plan/audit/2026-09-19-sole-backend-no-supabase.md`.

### ❌ What was NOT done

- No session-log entry and no audit file were written at the time (Rules 1 & 3 broken;
  now backfilled).
- No frontend wiring at all — 24 files still import `@/integrations/supabase/*`.
- No tests for any of the new routers; the 19 unit tests still only cover pure logic
  (pricing, coupons, payment helpers).
- No end-to-end run against a live Postgres/MinIO.
- `backend/README.md`, `infra/README.md`, and `app/db.py` comments were left describing
  the old Supabase design.

### 🐞 Found later (Session 4 review)

- `DATABASE_URL` examples use `postgresql://…` but the async engine needs
  `postgresql+asyncpg://…` → startup fails with `ModuleNotFoundError: psycopg2`.

## Session 4 — 2026-09-19

**Scope chosen by user:** put the whole project under version control so every change
can be reviewed, and report on what the previous session actually did.

### ✅ What was done

1. **Reviewed the working tree against the log** — discovered Session 3 above had
   never been recorded; reported it and backfilled the log + audit.
2. **Verified the current state** rather than trusting the docs: reinstalled the stale
   venv (`pip install -e ".[dev]"` — `passlib`/`minio` were missing), `pytest` →
   19 passed, `ruff check` → clean (fixed 2 pre-existing lint errors in the test file),
   `app.openapi()` → 34 paths / 40 operations, `docker compose config --quiet` → OK.
3. **Initialized git at the project root** (`main`), added a root `.gitignore`
   (Python/venv/caches, `.env`, node_modules, MinIO/Postgres volumes, the nested-repo
   backup), and — per user choice — **absorbed `vogue-vintage-vibes/` into the root
   repo** instead of keeping it nested or as a submodule.
4. **Committed the baseline in one commit per logical change** (frontend import,
   backend sole-service rewrite, infra stack, frontend `api.ts`, plan docs, env fix).

### ❌ What was NOT done

- No frontend typecheck/lint — `node_modules` is absent outside Docker, so `api.ts`
  is still unverified.
- No end-to-end stack run (no live Postgres/MinIO), no push to any remote.
- Stale readers left in place: `backend/README.md`, `infra/README.md`, `app/db.py`
  docstrings (listed in the Session-3 audit as open work).

### Decisions

- **One repo, one history:** the nested `vogue-vintage-vibes/.git` was set aside as
  `.git.orphan-backup/` (ignored) rather than deleted, so nothing is unrecoverable;
  that repo's history is also intact on `origin` (`github.com/bhrlu/vogue-vintage-vibes`,
  local `main` was in sync).
- Commits are split by logical change so each diff is reviewable on its own.

## Session 5 — 2026-09-19

**Scope chosen by user:** "now up the front end and backend in docker" — actually
run the Session-2 stack (which had never been started end to end).

### ✅ What was done

1. **Brought the whole stack up:** postgres + minio healthy, `minio-init` and
   `db-init` exit 0, backend healthy, frontend serving on :5173. Created the
   gitignored `infra/.env`; checked ports first (an unrelated project owns
   5433/8001/9002x/8080, so ours are free).
2. **Fixed the MinIO images:** MinIO stopped publishing free Docker Hub images in
   Oct 2025, so `minio/mc` *and* `minio/minio` both 404 (`pull access denied`).
   Moved to `quay.io/minio/minio` and dropped the `mc` image — the server image
   already ships `/usr/bin/mc`.
3. **Fixed 7 more runtime bugs** the stack exposed, all in the untested Session-3
   code: coupon seeding ran before the tables existed; **password hashing was
   entirely broken** (passlib 1.7.4 cannot load bcrypt ≥ 4.1 → every
   signup/login/seed raised `ValueError`); the coupon DDL still pointed at the
   deleted `auth.users`; `/search` and `/admin/stats` both 500ed on SQL issues;
   MinIO presigning used an int instead of a `timedelta` and signed for the
   in-cluster host; and the **payment callback always 404ed after a successful
   payment**, so orders never became paid. Details and root causes:
   `plan/audit/2026-09-19-docker-stack-up-and-runtime-fixes.md`.
4. **Verified the full purchase path end to end** (login → catalog → search →
   stock check → checkout with SANDE10 → payment → callback → paid order), plus
   admin views and the role guard (403 for customers on `/admin/*`), and a real
   presigned upload/download against MinIO.

### ❌ What was NOT done

- The repeat payment callback still returns 400 instead of `already_paid` — it
  needs the authority stored separately from `reference` (schema decision, left
  open).
- No test was added for any of the eight fixed bugs; the suite is still 19
  pure-logic tests (B3.5).
- Frontend still runs on Supabase — `src/lib/api.ts` remains unwired.
- No production compose (no TLS/workers/production build); no push to a remote.

### Decisions

- MinIO comes from `quay.io` (the only registry still publishing it); the
  version is frozen at the last release, which is acceptable for a dev stack.
- `passlib` was dropped rather than pinned back, since it is unmaintained and its
  `$2b$` output is format-compatible with the `bcrypt` library used instead.
- Payment presigning signs for the browser-reachable host with an explicit
  region, so no in-container round-trip is needed.

> ℹ️ Verification created local dev data on purpose: 2 orders (one paid, one
> pending), `tshirt-1` stock 25 → 23, and one test object in the MinIO bucket.
