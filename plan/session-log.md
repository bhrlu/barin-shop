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

## Session 6 — 2026-09-19

**Scope chosen by user:** (1) create a seed from the data in Supabase on the
frontend side; (2) then connect the frontend to the backend. Via multiple-choice,
the user picked **products + demo data** for the seed and a **full switch** for
the frontend, with the explicit instruction to keep a **researchable, resumable
todo list** updated after each API connection so a new session can continue.

### ✅ What was done

1. **Backend seeds** — `app/seed_products.py` (the 20 catalog products from the
   Supabase migration / `src/data/products.ts`, idempotent) and `app/seed_demo.py`
   (demo addresses, favorites and two orders for `customer@sande.local`), both
   wired into the compose `db-init` job before `seed_coupons`.
2. **Two backend endpoints** the frontend needed: `PATCH /auth/me` (profile save)
   and `GET /payments/mine` (customer payment history). 34 → 35 paths.
3. **Full frontend cut-over** — `src/lib/api.ts` is now the single data layer;
   auth/session, catalog + MinIO image signing, cart coupons, checkout, payment,
   cancel, account (orders/addresses/favorites/payments/profile) and admin
   (stats/orders/products/users) all call the FastAPI backend. The Supabase and
   Lovable integration folders and the two Supabase server-function files were
   **deleted**.
4. **Resumable tracker** — `plan/frontend-tasks.md` F1 rewritten as a per-file
   checklist with `[x]`/`[ ]` state and open decisions (A1), so this can be
   picked up in a later session.
5. **Verified** — backend: `ruff` clean, `pytest` 19 passed, OpenAPI 35 paths.
   Frontend (deps installed locally with npm): `tsc --noEmit` → 0 errors; ESLint
   on the changed set → only pre-existing warnings. Audit:
   `plan/audit/2026-09-19-seed-and-frontend-switch.md`.

### ❌ What was NOT done

- **No end-to-end run** — the stack was not started; no login → catalog →
  checkout → payment walk-through against the live backend.
- **Real Zarinpal redirect** not wired (payment page uses the backend's simulated
  gateway); **Google/OAuth login removed** (no backend OAuth).
- F1.5 search bar, F1.6 live stock, F1.7 admin stock still open.
- Repo-wide `eslint .` still fails on pre-existing prettier issues in untouched
  files (`account.favorites.tsx`, `admin.tsx`, and others) — left out to keep the
  diff scoped.
- `@supabase/supabase-js` remains in `package.json` (unused) to avoid churning
  the lockfile; `backend/README.md`/`infra/README.md` remain stale (B3.2/B3.3).

### Decisions

- **Full switch, not dual-run:** the browser talks to the backend directly; no
  TanStack server functions remain. This deletes the Supabase auth bridge rather
  than keeping two auth systems in sync.
- **Coupons:** only the applied *code* travels from cart → checkout (in
  `sessionStorage`); the discount is always recomputed server-side by
  `POST /checkout`.
- **Payment:** reuse the backend's simulated gateway endpoints
  (`payment-session` / `payment-complete`) to preserve the existing UX; the real
  Zarinpal flow is parked as decision A1.
- **Seed source:** the products are transcribed from the frontend's Supabase
  migration into a backend seed so a database not created by compose initdb still
  gets the catalog.

## Session 7 — 2026-09-19

**Scope chosen by user:** bring the Docker stack up and run the full
login → catalog → checkout → payment flow against the backend, fixing whatever
breaks.

### ✅ What was done

1. **Stack rebuilt and seeded** — `docker compose up -d --build` recreated
   `db-init` (running the new seed chain: `seed_auth → seed_products → seed_demo
   → seed_coupons`) plus `backend`/`frontend`; postgres/minio stayed up. Backend
   healthy, frontend ready on :5173.
2. **Fixed a real checkout bug:** coupon/stock errors raised
   `HTTPException(code, message, detail={...})` — two `detail`s → `TypeError` →
   **500**.
   `routers/checkout.py` and `routers/payments.py` now pass one `detail` object
   (`{message, code, issues}`), so those paths return proper 4xx with a message
   the UI already understands.
3. **Ran the whole flow green** (signup, catalog 20, coupon validate, checkout
   math 710,000, stock conflict 409, payment session + complete → paid,
   profile patch, payments/mine, admin 403 for customers, admin views, presigned
   upload → sign → GET). Also verified the frontend serves the new code, injects
   `VITE_API_URL`, transforms the changed modules, and passes CORS.
   Audit: [2026-09-19-e2e-flow-docker.md](audit/2026-09-19-e2e-flow-docker.md).

### ❌ What was NOT done

- **No headless-browser click-through** — the flow was driven through the same
  HTTP endpoints the UI calls, not a real browser session.
- **No regression test** for the `HTTPException` bug (needs the B3.5 DB fixture).
- Real Zarinpal redirect still parked (A1).

### Decisions

- Error `detail` is now a **structured object** (`message`, `code`, `issues`)
  for checkout/payment failures; `src/lib/api.ts` was already built to read it,
  so no frontend change was needed.
- The verification deliberately created dev data (two extra test customers,
  several orders, one MinIO object) — acceptable on the local dev stack.

## Session 8 — 2026-09-20

**Scope (user requests, in order):** (1) test all backend APIs and fix the 500 on
add-address; (2) translate the feature list to English and add a todo list;
(3) complete the backend API for Catalog & Products; (4) add a frontend todo
list; (5) document the design system; (6) commit everything; (7) update all
markdown docs, and codify a rule to do so after every task.

### ✅ What was done

1. **Fixed the reported 500.** `AddressOut.created_at` is `str`, but Postgres
   returns a `datetime`; Pydantic v2 rejected it → 500 on `GET` and `POST
   /addresses`. Reproduced against the schema, then isoformatted it in
   `routers/addresses.py` (the pattern the other routers already used).
2. **Full API test.** Brought up Postgres + MinIO, seeded, and wrote
   `tests/api_smoke.py` — logs in as customer + admin and hits every route.
   Result: **59 routes, 0 5xx**; the historical 500s in the container log are all
   from before the fix.
3. **Catalog & Products backend, complete.** Merchandising fields, extended
   filters/sort, per-variant (size × color) stock wired into stock-check and
   checkout, reviews + ratings + seller replies, search autocomplete + history,
   related/recommended/compare, recently viewed, and low-stock inventory. New
   tables/columns via idempotent startup DDL.
4. **Verified variant authority end-to-end** — 0-stock variant → check `ok:false`
   + checkout `409`; 2-stock → checkout succeeds and decrements to 1. Unit suite
   **25 passed**, ruff clean.
5. **Docs.** `plan/feature-roadmap.md` (English feature list + checklist),
   `vogue-vintage-vibes/DESIGN_SYSTEM.md`, `plan/frontend-tasks.md` Milestone F3,
   refreshed `backend/README.md` + `infra/README.md` + frontend README,
   `FEATURES.md` catalog/gap rows, and this log. Audit:
   `plan/audit/2026-09-20-catalog-backend-and-address-fix.md`.
6. **Committed** all work as `e2bd3f4` (61 files). Added `.freebuff/` to
   `.gitignore`.
7. **New Rule 5** in `plan/RULES.md` — update every affected doc before a task is
   considered finished.

### ❌ What was NOT done

- **No push** — the repo has **no git remote**, so the commit is local only.
  Needs a remote URL (see the commit message / audit).
- **No frontend wiring** for the new catalog endpoints — tracked as F3.
- **Variants are size × color only**; the "model" dimension is not modeled.
- **No stock reservation with TTL** — decrement happens at order creation.
- B3.4 (stale Supabase wording in code comments) left open; B3.7 payment
  authority persistence still open.

### Decisions

- **Commit locally, don't push** (user choice) — no remote configured.
- **Exclude `.freebuff/`** from the repo (user choice) — added to `.gitignore`.
- **Catalog DDL is additive at startup** rather than a migration, matching the
  existing coupon-table mechanism, so existing volumes need no manual step.
- **Variant stock is authoritative when present**, else the product aggregate is
  used — keeps legacy products working while enabling per-combination stock.

## Session 9 — 2026-09-20

**Scope (user request):** start **F3.0** — extend the frontend API client and
`Product` type so the catalog backend's new fields/endpoints are usable.

### ✅ What was done

1. Extended the `Product` type (`tags`, `badge`, `availability`, `available_at`,
   `low_stock_threshold`, `avg_rating`, `review_count`) and generalized
   `api.products()` to the full `ProductListParams` filter/sort set (backward
   compatible).
2. Added client methods for related / recommendations / compare / recently
   viewed / view tracking, variants, reviews, search suggestions + history, and
   the admin inventory + review-moderation + variant-CRUD surface.
3. Added the matching exported types.
4. **Verified:** `tsc --noEmit` → 0 errors. Backend catalog endpoints confirmed
   live earlier (50 OpenAPI paths, 59-route smoke 0 5xx).
   Audit: `plan/audit/2026-09-20-frontend-f30-api-client.md`.

### ❌ What was NOT done

- **No UI wiring** — F3.1–F3.6 (search box, variant picker, reviews UI, compare,
  admin screens) are untouched.
- `src/data/products.ts` legacy `Product` type and `toProduct()` were not bridged
  to the new fields (belongs with F3.2/F3.3).

### Decisions

- Keep the change **scoped to `src/lib/api.ts`** — F3.0 is the typed client
  surface; UI concerns are separate tasks.
- `api.products()` keeps accepting the old param shapes, so no existing caller
  changed.

### Addendum — catalog type bridge (F3.0 follow-up)

- **Done:** bridged the legacy `@/data/products` `Product` type and `toProduct()`
  in `@/lib/catalog` to the new catalog fields (`tags`, `badge`, `availability`,
  `availableAt`, `lowStockThreshold`, `avgRating`, `reviewCount`) so
  `useCatalog()` consumers can read them. `tsc --noEmit` → 0 errors.
  Audit: `plan/audit/2026-09-20-frontend-catalog-type-bridge.md`.
- **Decision:** catalog fields are **optional** on the legacy `Product` type (so
  the static seed still compiles) and **required** on `AdminProduct` (which is
  always built by `toProduct()` from a real API row).
- **Not done:** the unused static seed exports in `data/products.ts` remain dead
  code — separate cleanup.

## Session 10 — 2026-09-20

**Scope (user request):** check the frontend task list, confirm the backend APIs
are ready, read the design system, then start implementing.

### ✅ What was done

1. **Readiness check:** every F3 endpoint the frontend needs exists in
   `backend/app/routers/` (`/search`, `/search/suggest`, `/search/history` GET+
   DELETE, product detail/related/recommendations/compare/variants/reviews,
   `POST /products/{id}/view`, `/recently-viewed`, `/admin/inventory[/low-stock]`,
   `/admin/reviews`, `PATCH /reviews/{id}`, variant CRUD) and the F3.0 client
   already wrapped them. F3.1 is the first open item → implemented it.
2. **DESIGN_SYSTEM.md re-read before writing UI** — Persian/RTL copy, `@/`
   imports, `cn()`, brand tokens (`bg-sand`, `text-terracotta`, `bg-clay`
   skeletons), `toFa`, TanStack Query, `sonner`, existing `ui/*` primitives
   (`Popover`, `Input`).
3. **F3.1 Search implemented:**
   - new `src/components/HeaderSearch.tsx` — popover search with a 250 ms debounce
     on `GET /search/suggest`, product thumbnails signed via the new
     `resolveImageMap()`, category/tag/query/product kinds, plus a raw
     «جستجوی …» row; ArrowUp/ArrowDown + Enter keyboard flow.
   - search history for signed-in customers: recent queries in the dropdown,
     per-entry ✕ delete and «پاک کردن همه», each a `useMutation` that invalidates
     `["search", "history"]` and toasts on failure; signed-out visitors get a
     sign-in hint instead.
   - `shop.tsx` now parses `?q=` and renders a new `SearchResults` view (count,
     loading, error and empty states); the previous filter/sort page became
     `CatalogPage` and is untouched.
   - data layer: `searchQuery(q)` in `@/lib/catalog` maps `GET /search` hits to
     the local `Product` shape; `SearchHit`/`SearchResult` are now exported from
     `@/lib/api`.
4. **Verified:** `tsc --noEmit` 0 errors; eslint clean on the touched files;
   headless Chrome (DevTools pipe) against the live stack — dropdown opens and
   renders suggestions, ArrowDown+Enter lands on `/shop?q=شورت` with «۸ نتیجه»,
   `?q=zzzzqq` shows «۰ نتیجه» + empty state, plain `/shop` keeps its filters,
   and the signed-in history lists/deletes/clears correctly.
   Audit: `plan/audit/2026-09-20-frontend-f31-search.md`.

### ❌ What was NOT done

- F3.2–F3.6 (product page variants/reviews/carousels, server-side filters, admin
  screens) are untouched.
- Search results are not SSR-prefetched and have no filter sidebar (F3.3).
- `GET /search` does not match `tags`; logged as new **F3.1b** in
  `frontend-tasks.md`.
- `vite build` could not run in this environment (no `bun`; local Node 20.9 lacks
  `util.styleText`) — typecheck + live browser run used instead.

### Decisions

- **Search lives in `/shop?q=`** (no new route) so result URLs stay shareable and
  the route tree/`routeTree.gen.ts` needs no regeneration.
- `ShopPage` **dispatches** between `SearchResults` and `CatalogPage` instead of
  adding a branch to the existing body, so a search never fetches the full
  catalog.
- Suggestions navigate by kind: product → product page, known category →
  `?category=`, everything else → `?q=` (tags included, pending F3.1b).
- Did not reformat the 4 pre-existing prettier violations in `shop.tsx` to keep
  the diff minimal.

### Addendum — F3.1b backend tag search

- **Done:** `GET /search` now matches the `tags` array (`EXISTS … unnest(tags)`)
  and ranks it name > category > tag > description/material. Investigating showed
  the deeper problem: **no seeded product had any tags** (0/20), so tag
  suggestions could never fire and `?tag=` filtering was a no-op on the starter
  catalog. `app/seed_products.py` now tags all 20 products (material / fit /
  season vocabulary) and backfills tags **only on rows with none**, so an admin's
  own tags survive a re-run. `tests/api_smoke.py` gained a `check()` helper plus
  two assertions (tag query returns hits; suggest returns a `tag` kind).
  Audit: `plan/audit/2026-09-20-backend-search-tags.md`.
- **Verified:** `pytest -q` 25 passed, `ruff check app tests` clean,
  `tests/api_smoke.py` **63 routes/checks, 0 failed**; live `GET /search?q=زمستانی`
  now returns the one tagged product (it returned 0 before) and the browser shows
  «۳ نتیجه برای «کتان»» on `/shop?q=کتان`.
- **DB write (user-approved):** ran `python -m app.seed_products` inside the
  running backend container to backfill tags — idempotent, dev stack only.
- **Decision:** no tag-search unit test. `search_products` is pure SQL and the
  repo still has no pytest DB fixture (open under B3.5), so the live smoke checks
  carry it rather than a brittle string assertion on the SQL.
- **Not done:** tag filter chips / tag facets in the shop UI remain F3.3;
  `infra/initdb/02-public-schema.sql` intentionally untouched (the `db-init`
  seed step backfills tags on a fresh database in the same `compose up`).

## Session 11 — 2026-09-20

**Scope (user request):** build the **F3.2** product page — variant picker,
reviews section, related/recommended carousels.

### ✅ What was done

1. **New data layer:** `src/lib/variants.ts` (`comboStock` / `variantStockFor` /
   `defaultColor`) mirrors the backend's `app/services/variants.py` so the UI can
   never offer a combination checkout would reject; `@/lib/catalog` gained
   `productQuery`, `variantsQuery`, `reviewsQuery`, `relatedQuery`,
   `recommendationsQuery` and `toProducts()`.
2. **`components/product/VariantPicker.tsx`** — colour swatches + size buttons
   with per-combination availability, disabled sold-out/deactivated combos,
   disabled colours, and an `aria-live` stock line («فقط N عدد باقی مانده»).
3. **`components/product/ReviewsSection.tsx`** — average + 1–5 distribution,
   published list with seller replies and Jalali dates, star-input write/edit
   form (`POST` upserts), delete-own-review, guest sign-in link.
4. **`components/product/ProductRail.tsx`** — RTL embla rail with header arrows
   for related + recommended products.
5. **`product.$id.tsx` rewritten** — single-product fetch (`GET /products/{id}`),
   badge/discount/tags, availability states (`coming_soon`/`preorder` +
   `available_at` with a Persian date), quantity capped by the selected combo,
   view tracking, and an inactive-product 404 view.
6. **`formatFaDate()`** added to `@/lib/format` (Jalali dates, Persian digits).
7. **Verified:** `tsc` + eslint clean; headless Chrome (DevTools pipe) against
   the live stack for the product-level paths, and — with user approval —
   **temporary demo data (8 variants + two availability flips) created through
   the admin API, used to verify every combination/availability state, then fully
   reverted** (20 products back to `in_stock`, 0 variants).
   Audit: `plan/audit/2026-09-20-frontend-f32-product-page.md`.

### ❌ What was NOT done

- Cart/stock re-check on open remains F3.3/F3.5; `ProductCard` still shows no
  rating (F3.3).
- Product page is not SSR-prefetched.
- F3.4 (recently-viewed rail) and F3.6 (admin variants/inventory/reviews
  screens) untouched.

### Decisions

- **Variant selection defaults to the first colour that has stock** (pure
  function of product + variants, no effect) instead of blindly taking
  `colors[0]`.
- **Availability blocks ordering in the UI only** — `checkout`/`stock/check`
  ignore it, so this was logged as backend **B4.11** rather than faked in the UI.
- **Inactive products are no longer reachable on the storefront URL** (the page
  fetches by id and guards `active`), which is a small behaviour change from the
  catalog-cache based page.
- Demo data for verification was **created and reverted** (user-chosen option)
  so the dev DB keeps no throwaway rows.

## Session 12 — 2026-09-20

**Scope (user request):** **F3.3** — move shop filtering/sorting to the server
with availability/tag/badge/on-sale chips, ratings on cards, and compare.

### ✅ What was done

1. **`shop.tsx` is now URL-driven and server-filtered.** `validateSearch` parses
   and sanitises `category, size, color, maxPrice, sort, tag, badge, availability,
   onSale, q`; every chip is a `<Link>` so filters are shareable and survive a
   reload. The client-side `useMemo` filter over `useCatalog()` is gone — the list
   comes from `GET /products` (`toProducts()`), while `useCatalog()` still feeds
   the facet lists (sizes/colours/price bounds/tags). Price slider commits on
   release.
2. **`ProductCard`** shows `avg_rating` + `review_count` and gained a compare
   toggle; its root is now a wrapper `<div>` so the toggle is not a `<button>`
   nested inside the product `<a>`.
3. **Compare:** new `lib/compare.tsx` (localStorage `sandeh-compare-v1`, cap 4,
   `toggle()` returning added/removed/full), a sticky `CompareBar` rendered from
   `__root.tsx`, and a new `/compare` route (table via `ui/table`, `noindex`, per
   column remove, empty/error states). A footer link makes it discoverable.
4. **Verified:** `tsc` clean; eslint 0 errors on every touched file; headless
   Chrome (DevTools pipe) — tag/size/availability chips change the URL and the
   server result count (کتان ۳، پنبه ۸، پنبه+M ۵، به‌زودی ۰ + empty state), clear
   restores ۲۰, `?sort=rating` works, card ratings show «۵.۰ (۱ نظر)», compare
   toggles persist to localStorage, the bar appears, and `/compare` renders the
   comparison table with real values; remove/clear paths verified.
   Audit: `plan/audit/2026-09-20-frontend-f33-shop-filters-compare.md`.

### ❌ What was NOT done

- Multi-select size/colour (backend takes one value each) → **B4.12**.
- Tag chips are derived from the full cached catalog, not a facet endpoint.
- `?q=` search results still have no sidebar; no pagination; compare page shows
  product-level availability only.
- F3.4 (recently-viewed rail) and F3.6 (admin screens) untouched.

### Decisions

- **URL is the filter state.** No local filter state (except the slider draft),
  so back/forward and shared links behave like the category links already did.
- **Server does the truth:** result counts/empty states come from the filtered
  response, not a client re-filter.
- **Compare is client-side** (like the cart) rather than a backend list — no
  endpoint exists and the feature works fully offline of the account.
- Kept the existing `react-refresh/only-export-components` warning style for the
  provider+hook file, matching `lib/cart.tsx`.

## Session 13 — 2026-09-20

**Scope (user request):** **F3.4** — «بازدیدهای اخیر» rail on home/shop.

### ✅ What was done

1. `catalog.ts` gained `recentlyViewedQuery(limit)`; new
   `components/product/RecentlyViewedRail.tsx` wraps the existing `ProductRail`
   with it and renders **only** for signed-in customers with a non-empty list.
2. Rail mounted on the home page (after «جدیدترین‌ها») and at the bottom of the
   shop's `CatalogPage`.
3. The product page now invalidates `["recently-viewed"]` after a successful
   `POST /products/{id}/view`, so the rail is correct even if the visitor leaves
   before the request settles (otherwise the home fetch could race it).
4. **Verified:** `tsc` clean, eslint clean on the touched files; headless Chrome
   (DevTools pipe) — signed out there is no rail on `/` or `/shop`; signed in as
   the demo customer and after opening two products, both pages show the rail
   newest-first (crop-5 → tshirt-1 → older smoke-test views, 5 embla slides).
   Audit: `plan/audit/2026-09-20-frontend-f34-recently-viewed.md`.

### ❌ What was NOT done

- Guests still have no rail (endpoint requires auth, no merge with a local list).
- No clear/remove control (no `DELETE /recently-viewed` endpoint).
- Not added to the product page (it already has related + recommended rails), the
  `?q=` search view or the compare page.

### Decisions

- **Render nothing when empty or signed out** rather than an empty heading — the
  endpoint is per-customer, so a guest would otherwise always see a "no history"
  block on the home page.
- **Reused `ProductRail`** instead of a second carousel so all rails share one
  RTL implementation.
- **Invalidate after the view POST** rather than relying on mount-refetch timing.
