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

## Session 14 — 2026-09-21

**Scope (user request):** **F3.5** — wire the cart to `POST /stock/check` — and
**F3.6** — admin product-editor merchandising fields, variant editor, inventory /
low-stock screen, review moderation screen. Frontend only; all endpoints existed.
Audit: `plan/audit/2026-09-21-frontend-f35-f36-cart-stock-admin.md`.

### ✅ What was done

1. **Found and fixed a dormant client bug:** `POST /stock/check` takes a bare JSON
   array, but `api.stockCheck()` posted `{ lines: […] }` → **422**. The method had no
   callers before this session. Verified live: array → `200`, old shape → `422`.
2. **Cart re-validates stock on open and after every edit** (query keyed on the
   full line signature), shows a Persian per-line issue (`not_found` / `inactive` /
   `insufficient_stock` with the remaining count) and **blocks «تکمیل خرید»** while
   the API says `ok: false`. A failed request does not block — checkout re-validates
   server-side. A cart line whose product left the catalog now renders a
   «محصول حذفشده» row instead of nothing (it used to be unremovable).
3. **Admin product editor** gained `tags`, `badge`, `availability`, `available_at`
   (date input, disabled/cleared while `in_stock`) and `low_stock_threshold`;
   `ProductWrite` was extended to match `ProductIn`. List rows show the new
   merchandising state.
4. **New `components/admin/VariantEditor.tsx`** — per-product size × colour stock
   CRUD (create / edit stock+active / delete), opened per row; datalist-backed
   size/colour inputs; invalidates the admin list, the storefront variant query,
   the catalog and the inventory queries.
5. **New `/admin/inventory`** — `GET /admin/inventory` counters + threshold-aware
   `GET /admin/inventory/low-stock` report (products and variants).
6. **New `/admin/reviews`** — status filter, publish↔hide, seller reply, product
   names from the catalog, with catalog/review invalidation after each mutation.
7. Both routes added to the admin tab bar; `routeTree.gen.ts` regenerated (the
   plugin rewrote it when the route files appeared — diff is exactly two routes).
8. **Verified:** `tsc --noEmit` clean, eslint 0 errors on every touched file, plus
   live API checks against the Docker stack (stock check, inventory, low-stock,
   admin reviews, variant CRUD and review moderation/reply — the last two with
   temporary rows deleted again, `204`, no leftovers).

### ❌ What was NOT done

- **No headless-browser click-through** of the cart/admin screens (layout and the
  disabled-checkout state were not eyeballed).
- `vite build` is **not runnable in this environment** (pre-existing: Node 20.9 lacks
  `node:util.styleText` for rolldown; under Node 22 the installed rolldown is
  missing its `darwin-arm64` binding). Not caused by this change.
- Cart stock is not re-checked on window focus (**F3.5b**, added to the task file).
- No quantity capping from the reported `available`; no admin review delete; seller
  replies cannot be cleared (`ReviewReplyIn` requires `min_length=1`).
- `availability` enforcement in the API is still open (**B4.11**); admin lists are
  still unpaginated (**F2.5**).

### Decisions

- **Blocking is driven by the API's `ok` flag, never by a client re-derivation** —
  `StockIssue` carries only the product id (no size/colour), so the mapping helper
  attaches an issue to the single line of a product and only to unsatisfiable lines
  when a product occupies several; the *decision* to block still comes from the
  server response.
- **A failed stock check does not block checkout** — `POST /checkout` re-validates
  and prices server-side, so a transient fetch error must not trap the customer.
- **Variant edit is explicit (save button), not on-blur**, so no request fires while
  the admin is still typing.
- **Review moderation is hide/publish only** — the delete endpoint stays unused in
  admin so a hidden review keeps its history/reply.
- **Kept the legacy cart money rules untouched** (۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰)
  and the storefront totals client-side; `stock/check`'s `subtotal` is not used for
  display.

## Session 15 — 2026-09-21

**Scope (user request):** **B4.11** (enforce `availability` in the API) and
**B4.12** (multi-value size/colour filters), plus the shop's multi-select chips
(**F3.3c**) so the filters are usable end to end. Audit:
`plan/audit/2026-09-21-backend-b411-b412-availability-multifacet.md`.

**User decisions:** block **both** `coming_soon` and `preorder` (one reason, no
per-state code); **include** F3.3c in this pass.

### ✅ What was done

1. **`app/services/availability.py`** — `availability_issue()` is the single gate;
   a missing/null column still counts as orderable so pre-migration rows cannot
   start failing. Applied in `routers/stock.py` **and** `services/checkout.py`
   (inside the `FOR UPDATE` lock), before the size/variant/stock checks.
2. **`preorder` is not orderable** — the order schema has no preorder flag, so
   allowing it would promise a delivery the model cannot express. Enabling it later
   is a one-function change plus the flag → **B4.13**.
3. **`StockIssue.reason` is a documented closed set** (`not_found`, `inactive`,
   `not_available`, `size_invalid`, `insufficient_stock`). `size_invalid` was
   already emitted by checkout but was missing from the schema and the frontend
   type; `/stock/check` now uses it for an unavailable size instead of reporting a
   stock problem. Same HTTP shapes as before (**409 `stock_conflict`** on checkout,
   200 with `ok:false` on the pre-check) — no status string changed.
4. **`app/services/catalog_filters.py`** — `split_multi()` accepts repeated and/or
   comma-separated facets. `GET /products` takes `list[str]` for `size`/`color`, OR
   within a facet / AND across, resolved **per combination** so a variant-deactivated
   pair is not advertised (a missing variant row still falls back to aggregate
   stock, per the stock model).
5. **Shop sidebar is multi-select** (F3.3c): `size`/`color` are `string[]` in the
   route search, chips toggle with `aria-pressed`, headings marked «چند انتخابی»,
   `clean()` drops empty arrays, and `api.products()` sends **repeated** params.
6. **`src/lib/stock-issues.ts`** — one copy of the Persian copy per reason, shared
   by the cart line note and the checkout toast (which is no longer «موجودی کافی
   نیست» for a non-stock rejection). The cart uses the product's own `availability`
   to say «پیش‌فروش» vs «هنوز عرضه نشده», since the API reports one reason.
7. **Verified:** 39 unit tests (14 new) + ruff clean; live Docker stack — repeated
   == comma facets, OR widens (16→20 for `M,36-38`), AND across facets (11),
   empty/bogus facet values are safe, `coming_soon`/`preorder` → `not_available` in
   both endpoints with **no order written**, an inactive variant drops the product
   from the exact-pair filter while widened facets keep it, and every temporary row
   was removed afterwards (availability restored, `variants: []`, all products
   `in_stock`). `tests/api_smoke.py` now asserts the guard and the facet shapes:
   **76 checks, 0 failed**. Frontend `tsc` clean, eslint clean on the touched files.

### ❌ What was NOT done

- **No browser pass on the shop chips** — `vite` cannot run in this environment
  (pre-existing: Node 20.9 lacks `node:util.styleText` for rolldown; under nvm
  Node 22 the installed rolldown has no `darwin-arm64` binding), so the chip
  toggling is verified by types + the URL contract, not by clicking.
- `preorder` remains unorderable (deliberate, → B4.13); no facet **counts** on the
  chips; the filter answers "offered", not "in stock" (an active variant at stock 0
  still matches); tag chips still come from the cached catalog.
- `infra/README.md` and `vogue-vintage-vibes/README.md` untouched on purpose — no
  compose/env/script change (the frontend README carries no component inventory).

### Decisions

- **One reason for both unavailable states** (`not_available`) per the user's
  choice; the storefront adds the nuance from the product's own `availability`
  rather than the API duplicating it.
- **The gate lives in a shared service**, not duplicated in the two endpoints, so
  the pre-check and the order can never disagree — the same reasoning as
  `services/variants.py` and `services/catalog_filters.py`.
- **Per-combination facet semantics** instead of the naive cross-product: a
  deactivated size×colour pair must not be advertised, while a pair with no variant
  row keeps the product (it is purchasable through aggregate stock).
- **Repeated params, not comma-joined** (the client appends one param per value) —
  both work server-side, but repeated is what `URLSearchParams` gives naturally, so
  the URL stays readable and canonical.

## Session 16 — 2026-09-21

**Scope (user request):** add a rule that
`design/SANDE_FULL_DEV_SPEC.md` must be checked **before starting each task**.
Audit: `plan/audit/2026-09-21-rule-spec-preflight.md`.

**User decisions:** authority is **"read first, current stack wins"** (follow the
spec where it applies; the live FastAPI architecture beats its Supabase/Lovable
stack section; report deviations in the audit), and the rule applies to **every
task, no exceptions**.

### ✅ What was done

1. **`AGENTS.md`** — new always-loaded section *«Mandatory: read the dev spec before
   the task starts»*, sitting above the existing end-of-task docs checklist so both
   ends of a task are covered; the audit contents now include a **spec check**, and
   the standing rules link to the detailed version.
2. **`plan/RULES.md`** — **new Rule 0** (follow where it applies / live repo wins on
   conflict / report in the audit / reconcile but don't edit the spec), **new Rule
   4b** (checked at both ends — no spec line in the audit means the task is not
   finished), a **Spec check** bullet in Rule 1, and a Rule 4 wording fix: it no
   longer claims "the Supabase schema" is the protected behaviour (that stopped
   being true when Supabase was removed; the protected content — status strings and
   cart money rules — is unchanged).
3. **`plan/README.md`** — the spec is indexed at the top with its precedence note,
   and the short rules lead with Rule 0.
4. **`design/SANDE_FULL_DEV_SPEC.md` was not modified** — it is the user's document
   (Rule 0.4); the staleness that matters (stack header, Part C statuses, the
   `formatPrice`/`toPersianDigits` helper names vs this repo's `formatToman`/`toFa`)
   is recorded as open work in the audit instead.

### ❌ What was NOT done

- **No reconciliation of the spec with the repo** (its Supabase/Lovable stack, its
  `AdminLayout`/`DataTable`/`OrderDetailSheet`/`admin.refunds`/`admin.coupons`
  targets, `@tanstack/react-table`, RHF+Zod, helper names, stale Part C statuses).
  Logged as open in the audit; it is a user-facing document change nobody asked
  for yet.
- **No checkbox in the task lists** — a process rule is not backend or frontend
  work (stated in the audit per Rule 5).
- **No automated enforcement** — the rule is convention + review, like the audit
  rule itself.
- `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
  `FEATURES.md`, `feature-roadmap.md`, `DESIGN_SYSTEM.md` untouched — no endpoint,
  feature, component or setup change.

### Decisions

- **Two-layer rule, like the rest of the working agreement:** the always-loaded
  one-paragraph version in `AGENTS.md`, the detailed obligations in
  `plan/RULES.md` Rule 0, so a future agent that only reads one of them still gets
  the precedence right.
- **The spec never silently overrides reality.** Explicit "the live repo wins"
  clause rather than a blanket "follow the spec", because part of the document
  describes a stack this project deliberately left behind.
- **The spec is read-only for agents.** Staleness is fixed in the plan docs, not by
  editing the user's document, so their copy stays authoritative for their intent.
- **A conflict is a finding, not a failure** — audits must name contradictions, so
  the rule produces information instead of forcing a wrong implementation.

## Session 17 — 2026-09-21

**Scope (user request):** update `vogue-vintage-vibes/DESIGN_SYSTEM.md` with
`design/SANDE_FULL_DEV_SPEC.md`. Audit:
`plan/audit/2026-09-21-design-system-spec-merge.md`. Doc-only change — no code,
schema, endpoint or test was touched.

### ✅ What was done

1. **`DESIGN_SYSTEM.md` rewritten as one merged guide** with two labelled layers:
   **Now** (true of the code) and **Target** (from the spec, for new work), preceded
   by the provenance + precedence note (Rule 0.2).
2. **Spec content folded in:** the palette's *meaning* as a new **§2.3 status
   semantics** table (positive/in-progress/waiting/negative/commerce mapped onto the
   existing tokens, since the spec's own B1.1 forbids the raw `emerald/amber/rose`
   classes its B0.2/B4.2 prescribe), **§2.5** typography (`font-display`, and the
   missing `--font-mono` the spec assumes), new **§2.6** spacing/borders/elevation
   and **§2.7** micro-interactions, a new **§3.3** table mapping [FE-01]–[FE-08] to
   what exists today, the **B1 invariants** merged into **§4**, the **B4** snippets
   rewritten against real helpers (`formatToman`/`toFa`), and the **B5** pre-flight
   list merged into **§9**.
3. **New §5 precedence table** — 10 conflicts (`Supabase`/`createServerFn`,
   `order-actions.functions.ts`, helper names, raw status colours, toast position,
   radii, admin components, `bg-muted`, `font-serif`/`font-mono`, print CSS) each with
   the binding side, so Rule 0.2 never has to be re-derived for the same question.
4. **New work logged (Rule 2):** `plan/frontend-tasks.md` **Milestone F4** (F4.1
   token-driven status badges, F4.2 sidebar admin shell, F4.3 reusable data grid,
   F4.4 order drawer + invoice print, F4.5 coupons manager) and `plan/backend-tasks.md`
   **Milestone B5** (B5.1 audit log, B5.2 KPI aggregation range endpoint, B5.3 refund
   bank-tracking columns + the `requested` vs `pending` vocabulary mismatch, B5.4
   granular staff roles).
5. **Claims verified against the code** before writing them: toaster is
   `top-center`; `@tanstack/react-table` is not installed; `zod` is imported nowhere
   and RHF only by the unused `ui/form.tsx`; no `--font-mono` and no `@media print`;
   `rounded-none` is pervasive; both order chips render terracotta/sand; and
   `refund_requests` has only `status`/`admin_note` with a `requested` default.

### ❌ What was NOT done

- **`design/SANDE_FULL_DEV_SPEC.md` was not edited** (Rule 0.4): its stale stack
  header, `order-actions.functions.ts`/`formatPrice`/`toPersianDigits` references, raw
  palette badge classes and Part C statuses stay as they are — §5 of
  `DESIGN_SYSTEM.md` carries the corrections instead.
- **Nothing was implemented:** status badges, `--font-mono`, the print stylesheet,
  the sidebar shell, the data grid, refunds/coupons screens and the audit log are
  specified but unbuilt (F4.x / B5.x).
- **No lint/test guardrail** for the new rules (no lint rule blocks `rounded-none` on
  an admin widget or a raw palette class) — §9's checklist is still the only guardrail.
- `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
  `FEATURES.md`, `plan/feature-roadmap.md` untouched — no capability, endpoint or
  setup step changed.

### Decisions

- **One document instead of two contradicting ones**, with the spec's rules marked
  Now/Target rather than silently dropped or silently adopted — the spec stays
  readable as intent, the code stays the truth.
- **The spec's own contradiction is resolved in favour of its B1.1 invariant**: state
  colour is expressed through this project's semantic tokens (§2.3), not the raw
  `bg-emerald-50 …` classes from its B0.2/B4.2 — with the `--status-*` escape hatch
  documented if literal green/amber/rose is ever wanted.
- **`terracotta` is reserved for brand/CTA, `destructive` for negative state** —
  today's uniform terracotta chip for every order status conflates the brand accent
  with "danger", which the status table now fixes.
- **Precedence is written down once (§5), not argued per task** — the spec is read,
  the repo wins where they conflict, and the audit records which side was taken.
- **Storefront corners and toast position stay as they are** (grandfathered); the
  spec's `rounded-xl/2xl` + no-`rounded-none` rule applies to **new admin data
  widgets** only, so existing screens are not churned for a doc change.

---

## Session 18 — 2026-09-21

**Scope (user request):** continue the remaining **backend + frontend** work,
**excluding admin tasks**. Audit:
`plan/audit/2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md`.

Chosen slice — the customer-facing items whose dependencies were already in place:
B3.7 (payment authority), B3.4 (Supabase wording), F2.1 (contact form), F2.7
(default address in checkout), plus the checkout `province` gap the spec check
surfaced.

### ✅ What was done

- **B3.7** — `payments.authority` (+ index) created idempotently on startup;
  `verify_and_finalize` resolves by authority with a `reference = :authority`
  fallback for pre-column rows and returns `already_paid` for a settled session.
  A repeat Zarinpal callback is now a 303 redirect to the order page, not a 400.
- **B3.4** — the last Supabase mentions in `app/db.py`, `models.py`,
  `routers/auth.py`, `routers/storage.py`, `seed_products.py` now describe the
  FastAPI + own-JWT + MinIO reality.
- **B3.9 / F2.1** — `contact_messages` table, public `POST /contact`
  (guest-friendly, `user_id` NULL), admin `GET /admin/contact-messages?status=` +
  `DELETE /admin/contact-messages/{id}`; `contact.tsx` is a real form with
  API-mirrored validation and Persian toasts.
- **B3.10 / F2.7** — the address book enforces **one** default per customer
  (first address becomes it, explicit flag moves it, deleting the default promotes
  the survivor) and gained `PATCH /addresses/{id}`. The account tab shows a
  «پیشفرض» badge and can move/create defaults; checkout offers saved addresses,
  pre-selects the default and pre-fills the form.
- **Checkout `province`** — the spec's [FE-05] shipping box asks for it, saved
  addresses had it, and the checkout payload silently dropped it. Added as an
  optional API field (`province: str | None`, so older payloads keep working),
  stored in `orders.shipping_address`, and added to the form.
- `src/lib/api.ts` gained `ContactMessage`, `api.contact()`, `api.updateAddress()`
  and `CheckoutAddress.province`.

### ❌ Explicitly not done

- **No admin screens** (per the instruction): no contact inbox (F2.1b), no refunds
  page (F2.4), no dashboard charts (F2.6), no pagination (F2.5). `plan/ADMIN-BACKEND_TASKS.md`
  and `plan/ADMIN-FRONTEND_TASKS.md` were left untouched — only indexed in
  `plan/README.md` so they stop being invisible.
- **F2.3 forgot-password** — still needs a reset-token endpoint plus outbound email
  (B2.1), so it was not started.
- **F2.8 tracking number** and Milestone **B2** (notifications, exports, invoices,
  jobs) — untouched, both larger than this slice.
- **No browser pass** — `vite` still cannot start in this environment (pre-existing
  Node/rolldown binding issue), so the UI was verified with `tsc` + eslint and by
  the API shapes it reads, not by clicking.
- `infra/initdb/02-public-schema.sql` deliberately untouched: `contact_messages`
  and `payments.authority` are additive DDL applied by `app/db.py`, the existing
  convention for coupons/variants/reviews/search_history/recently_viewed.

### Decisions

- **Non-admin slice first, admin split left alone.** The user's constraint was
  explicit, and the admin docs are a separate task file; mixing them would make the
  audit's scope line meaningless.
- **`province` made optional rather than required** — the checkout schema is a
  public contract and the frontend deploys separately from the API, so a required
  field would break in-flight clients for a cosmetic gain.
- **Guest-friendly contact endpoint.** Requiring an account to ask about a size or
  an order would have been the wrong trade; the sender's own `contact` field is the
  reply channel, and the missing spam guard is logged as B3.11 instead.
- **`is_default` invariant enforced server-side, not in the UI.** The UI only ever
  asks for "make this the default"; the "at most one" rule lives in one SQL helper
  so no future screen can violate it.
- **Checkout keeps its uncontrolled FormData fields.** Addressing the pre-fill with
  a remount key avoids converting a working, simple form into controlled state.

---

## Session 19 — 2026-09-21

**Scope (user request):** let customers edit the fields of a saved address in the
account tab. Audit: `plan/audit/2026-09-21-frontend-f27b-edit-address.md`.
Frontend-only change — `PATCH /addresses/{id}` already existed (B3.10).

### ✅ What was done

- `account.addresses.tsx`: the seven address inputs moved into a shared
  **`AddressFields`** component (with a `prefix` so the create form and an open edit
  form never collide on input ids). Each card gained a **«ویرایش»** action that opens
  an inline pre-filled form with «ذخیره تغییرات» / «انصراف»; only one card is open at
  a time and deleting the open card closes it.
- The edit request sends **fields only** — no `is_default` — so fixing a typo can
  never move or clear the default that checkout pre-fills. A comment in the mutation
  says why.
- `api_smoke.py`: new live assertion **`PATCH fields only edits without touching
  is_default`** — the exact request shape the UI now sends. Smoke is 99 checks,
  0 failed.

### ❌ Explicitly not done

- **No backend change** — `AddressUpdateIn` already treats every field as optional,
  which is what makes a fields-only patch safe. `backend/README.md` and
  `infra/README.md` untouched (endpoint, setup, scripts unchanged).
- **No browser pass** — `vite` still cannot start here (pre-existing Node/rolldown
  binding issue), so focus/scroll behaviour after opening the edit form is unverified.
- **The edit form does not own `is_default`** — deliberate (see above). If the form
  should toggle it too, that is a follow-up decision, not an oversight.

### Decisions

- **Fields-only patch instead of sending the whole row.** Sending `is_default` back
  with every edit would make an innocent title change able to demote the default
  address (or promote a non-default one) depending on the row's state — the flag
  stays behind its own explicit action.
- **One shared field component rather than a copy.** The edit form must stay in sync
  with the create form (both mirror the backend's `AddressIn`), so the field list
  exists once; the `prefix` prop is the price of uniqueness.
- **Inline edit rather than a modal.** The tab is a short list on a storefront page;
  swapping the card keeps the surrounding addresses visible and needs no new
  primitive.

---

## Session 20 — 2026-09-21

**Scope (user picked "quick wins batch"):** F2.1b admin contact inbox + F2.4 admin
refunds page + F2.8 shipment tracking number. Two small backend pieces were needed
and logged first as new checkboxes (Rule 2): B3.12 (`orders.tracking_code` + PATCH)
and B3.13 (mark a contact message answered).
Audit: `plan/audit/2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md`.

### ✅ What was done

- **Backend:** idempotent `TRACKING_DDL` adds `orders.tracking_code` (NULL until an
  admin sets it); `PATCH /orders/{id}` accepts it (max 60 chars, empty clears,
  admin-only); `_ORDER_SELECT` returns it. New `PATCH /admin/contact-messages/{id}`
  with `Literal["new","answered"]` validation. Smoke gained 8 checks (mark answered,
  `?status=answered`, 422 on bogus, save/customer-visibility/clear/403 on tracking).
- **Frontend:** two new admin tabs — `/admin/messages` (F2.1b inbox: filters,
  copy contact, mark answered/reopen, delete) and `/admin/refunds` (F2.4: three
  [FE-06] tabs, claim cards, approve/reject/settle dialog). F2.8: tracking input in
  each admin order row + «کد رهگیری مرسوله» on the customer order page. `api.ts`
  got the types/methods; `orders.ts` got `REFUND_STATUS`.
- **Verified:** pytest 39 passed, ruff clean, `tsc --noEmit` clean, live smoke
  **117 routes/checks, 0 failed** against the running Docker stack (API hot-reloaded).
- **Docs:** both task lists, this log, `backend/README.md`, `FEATURES.md` (gaps
  ۶.۳/۶.۱۰/۶.۱۴), `DESIGN_SYSTEM.md` (§3.3 + §8.9), `plan/README.md`, audit file.

### ❌ Explicitly not done

- **Refund bank-tracking input** — needs B5.3 (`bank_tracking_code` column +
  vocabulary decision); the dialog records the admin note only.
- **Order drawer / invoice printing** (F4.4) untouched — the tracking input lives
  in the order row; the drawer remains the spec-aligned follow-up.
- **`vite build` still fails in this shell** (pre-existing npm-vs-Bun `node_modules`
  + Node 20.9 vs rolldown requirement). `tsc --noEmit` passes; the container build
  (Bun) is the reliable path. Not attempted to fix here.
- **No notification** on tracking/refund events — B2.1, untouched.

### Decisions

- **Settlement records the note only, no fake bank-tracking field.** A required
  input with nowhere to persist it would drop data silently; B5.3 unblocks it.
- **`REFUND_STATUS` keeps `requested` as a known label** so pre-existing rows
  never render raw keys, and unknown future statuses fall back to the raw string.
- **Empty tracking code = clear** (mirrors `PATCH /addresses` semantics), so a
  typo can be removed without a dedicated endpoint.
- **Payment-session `tracking_code` left alone.** Same field name, different
  meaning (simulated gateway session code); changing it would break Rule 4
  contracts for nothing.

---

## Session 20b — 2026-09-21 (same day follow-up)

**Scope (user request):** rebuild the frontend `node_modules` with Bun and get
`vite build` passing locally — the Session 20 open item.

### ✅ What was done

1. **Installed Bun on the host** (1.4.2, matches the container's) via the official
   installer into `~/.bun` — the host previously had none.
2. **Removed the npm-installed `node_modules`** (it was built against npm's
   optional-deps layout, which is why rolldown's `@rolldown/binding-darwin-arm64`
   native binding was missing).
3. **Fixed the lockfile registry** — 10 packages (the `@lovable.dev/*` pair, the
   `@supabase/*` set that supabase-js pulls in, and `iceberg-js`) resolved from
   `europe-west1-npm.pkg.dev/lovable-core-prod/sandbox-npm-cache/`, a private
   Lovable registry that 403s outside their infra. All 10 exist on public npm as
   the **same tarballs at the same versions** (verified: identical paths, same
   SRI hashes verified by bun on install), so the lockfile's host prefix was
   repointed to `registry.npmjs.org`. A backup of the old lockfile went to
   `/tmp/bun.lock.bak`.
4. **`bun install`** — complete dependency tree restored (333 MB, vite +
   `@rolldown/binding-darwin-arm64` present).
5. **`bun run build`** with Node 22 — **passes** (671 ms, full `.output/` SSR
   bundle). `tsc --noEmit` clean.

### ❌ Explicitly not done

- No code changes; the frontend still pins the same dependency versions.
- `infra/frontend.Dockerfile`'s `overrides` entry kept (now a harmless safety
  net) — deleting it belongs to an infra task, and it does no harm.

### Decisions

- **Repoint the lockfile host rather than adding `overrides` to package.json.**
  The tarballs are byte-identical on the public registry, bun verifies SRI
  hashes on install, and the lockfile stays the single source of truth for
  versions. The alternative (a package.json override per private package) would
  have grown a second place where dependency truth lives.
- **Documented the Node ≥ 20.12 requirement** in `vogue-vintage-vibes/README.md`
  (system Node 20.9 fails on rolldown's `styleText` import; Node 22 from nvm
  works).

### Doc updates in this follow-up

`vogue-vintage-vibes/README.md` (Development note: registry + Node version),
`infra/README.md` (frontend build note), `infra/frontend.Dockerfile` (header
comment), `plan/session-log.md` (this section). The Session 20 audit's open item
"vite build fails in this shell" is now resolved; the audit file itself is not
retroactively edited — this session entry supersedes it.

---

## Session 20c — 2026-09-21 (same day follow-up)

**Scope (user request):** delete the now-redundant `overrides` entry from
`infra/frontend.Dockerfile` and verify the image still builds.

### ✅ What was done

- `frontend.Dockerfile`: removed the `bun -e … overrides` JSON-munging RUN; the
  install step is now a plain `RUN bun install`. Header comment rewritten: the
  lockfile has been fully public since 2026-09-21, and if it ever regresses to a
  private tarball URL the build now fails loudly at `bun install` (good) instead
  of being silently patched around.
- **Image build verified:** `docker build -f infra/frontend.Dockerfile -t
  sandeh-frontend:test-override-removal .` from the repo root → success
  (~6.5 min cold; the COPY layer cache invalidation forced a full re-install).
- **Image contents verified:** inside the image — `@lovable.dev/cloud-auth-js` +
  `vite-tanstack-config` present, `vite` present, linux rolldown bindings
  present, `overrides` count in package.json = 0, zero `pkg.dev` URLs in the
  copied lockfile.
- **Runtime verified:** ran the image twice with compose-equivalent mounts
  (source rw + anonymous `node_modules` volume): first boot showed
  `Resolving dependencies` — the anonymous volume starts **empty** and bun
  installs into it on start, so the first `bun install` at build time only
  primes the image, not the volume (this was true before the change too). With
  the volume primed, the container served `HTTP 200` with the SÂNDÉ title/brand
  in the HTML, 0 errors in the vite log.
- Running `sandeh-*` stack untouched throughout (still Up 47h, backend health
  200). Test containers/volume/image cleaned up.

### ❌ Explicitly not done

- No `docker compose up -d --build` on the live stack — the running frontend
  container keeps its 47-hour-old image until the user chooses to rebuild.
- No commit; all changes remain in the working tree.

### Decisions

- **Loud failure preferred over silent patching.** Keeping the override meant a
  private-registry regression would go unnoticed (the override would mask it).
  A plain `bun install` makes the lockfile the single point of truth, verified
  by SRI hashes at build time.
- **Kept the same base image and CMD** — the change is the removal of one RUN
  step, nothing else.

---

## Session 21 — 2026-09-21

**Scope (user request):** B5.3 — refund bank-tracking fields — the next open
backend task. Completes the settlement half of the F2.4 refunds centre.
Audit: `plan/audit/2026-09-21-backend-b53-refund-bank-tracking.md`.

### ✅ What was done

- **Schema (idempotent `REFUND_DDL`):** `refund_requests` gained
  `bank_tracking_code`, `resolved_by` (FK → users) and `resolved_at`; a startup
  UPDATE normalizes legacy `requested` rows to `pending` (new rows insert
  `pending` explicitly). New `RefundRequest` ORM model documents the shape.
- **API:** `PATCH /refunds/{id}` requires a non-blank bank code when settling
  (422 otherwise), stores it via COALESCE (re-settlement updates, never wipes)
  and stamps `resolved_by` + `resolved_at` on every resolution;
  `GET /admin/refunds` now carries the claimant's name/email.
- **UI (F2.4 completion):** the settlement dialog takes the required Paya/Satna
  code (dir=ltr, mono, button disabled while empty — mirroring the backend);
  claim cards show the claimant; settled cards show the code + settlement date.
- **Cleanup:** deleted the stale `vogue-vintage-vibes/package-lock.json` (npm
  artifact from this morning's broken install; `bun.lock` is the only lockfile).
- **Verified:** pytest 39 passed, ruff clean, tsc clean, vite build passes, live
  smoke **130 routes/checks, 0 failed** (full refund flow asserted end-to-end).
- **Docs:** backend-tasks (B5.3 ticked), frontend-tasks (F2.4 updated), audit,
  backend/README, FEATURES ۶.۱۰, DESIGN_SYSTEM §3.3, plan/README, this log.

### ❌ Explicitly not done

- Sheba/card-number capture ([FE-06] pictures one) — no column, no task.
- SMS/email on settlement (B2.1) and the admin audit-log entry for the
  resolution (B5.1) — both still open.
- `admin_notes` (spec plural) not renamed — the existing `admin_note` column is
  the contract (Rule 4).

### Decisions

- **Bank code required server-side, not just in the UI.** [FE-06] calls it
  required; enforcing it in `resolve_refund` means no client can settle an
  untraceable refund, and the disabled button merely mirrors the 422.
- **COALESCE for the code** so correcting a typo on re-settlement works without
  a settlement ever losing its code.
- **Vocabulary normalization is one UPDATE, not a constraint** — a CHECK
  constraint would break rows the running store already holds (Rule 4); the
  UPDATE only rewrites the exact legacy value.
- **User choice from the spec's two options (Rule 0.4):** the plan docs now
  describe `pending` as the canonical initial state; the DDL default stays
  `requested` in infra (untouched per Rule 4) but nothing inserts it any more.

---

## Session 22 — 2026-09-21

**Scope (user request):** the ADMIN-*.md files are the spec epics; the main task
lists pointed at B5.2 + F2.6 (FE-09/FE-03) as the next unblocked pair, shipped
as one unit since F2.6 was blocked on B5.2.
Audit: `plan/audit/2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md`.

### ✅ What was done

- **B5.2** — `GET /admin/kpis?range=today|7d|30d|all`: gross/net revenue, paid
  orders, AOV, pending refunds, low-stock (per-product threshold), a daily
  revenue series (paid, non-cancelled), a status breakdown, and deltas vs the
  preceding window (`all` → null deltas). Unknown range → 422.
  Found live: asyncpg refuses `CAST($1 AS interval)` — the whitelisted interval
  literal is inlined instead.
- **F2.6** — `/admin` rewritten: range selector, 4 KPI cards with delta badges,
  recharts revenue area chart (terracotta gradient, Persian tooltip), status
  donut with token-driven colours + legend, amber urgent-actions callout
  (links to refunds/inventory), skeletons, latest-orders preserved via the
  existing `adminStats` query.
- **Verified:** pytest 39 passed, ruff clean, tsc clean, vite build passes,
  live smoke **138 routes/checks, 0 failed** (KPI block-shape + 8-point series
  asserted).
- **Docs:** both task lists ticked, audit, backend/README endpoint table,
  DESIGN_SYSTEM note, plan/README, this log.

### ❌ Explicitly not done

- F4.x admin shell/data-grid chrome — dashboard stays in the tab shell.
- B5.1 audit log (next backend epic), B2.2 sales reports (gap ۶.۱۲ unchanged).
- Chart lazy-loading for the admin chunk — perf follow-up only.

### Decisions

- **Deltas compare window vs preceding window** (7d vs previous 7d), not
  calendar months — matches the range selector; the spec's MoM badge intent is
  preserved visually.
- **Low-stock uses each product's own threshold** (spec's flat «<5» is the
  default) — the repo's per-product column is the better rule.
- **Series interval inlined from the whitelist** rather than a bound parameter;
  the whitelist makes it injection-safe and the comment in the code says why.

---

## Session 23 — 2026-09-21

**Scope (user request):** B5.1 — admin audit log with writes on privileged
mutations (spec BE-04).
Audit: `plan/audit/2026-09-21-backend-b51-audit-log.md`.

### ✅ What was done

- **Schema:** idempotent `AUDIT_DDL` — `audit_logs(admin_id FK→users, action,
  entity_type, entity_id, old_values JSONB, new_values JSONB, ip_address,
  created_at)` + created_at and (entity_type, entity_id) indexes.
- **Service:** `app/services/audit.py::record_audit` — inserts on the caller's
  session so the entry commits atomically with its mutation; a failing audit
  insert logs and rolls back instead of breaking the request. Closed ACTIONS
  vocabulary.
- **Wired:** orders (status / payment_status / tracking_code with real old→new
  captured before the UPDATE), cancel, refund resolution (bank code + note),
  product & variant & coupon CUD (tracked fields old→new), review moderation
  and admin deletions. Customer review deletions deliberately not audited.
- **Read API:** `GET /admin/audit-logs` (admin-only; filters action /
  entity_type / entity_id / admin_id; joined admin_email/admin_name).
- **Verified:** pytest 39 passed, ruff clean, live smoke 0 failed (audit
  entries appear with admin identity; entity filter works; customer gets 403).
- **Docs:** B5.1 ticked + two follow-up checkboxes (B5.1a IP capture, B5.1b
  DB-level append-only), audit, backend/README, plan/README, this log.

### ❌ Explicitly not done

- IP capture (B5.1a) and DB tamper-resistance (B5.1b) — split off as checkboxes.
- No admin UI for the trail (belongs to F4.x shell work).
- Role changes not auditable until B5.4 exists.

### Decisions

- **Audit insert shares the mutation's transaction** — an admin action must
  never exist without its trail entry (and vice versa); `record_audit` failing
  logs rather than raises so the audit layer can never take down a legit
  mutation.
- **One entry per changed facet on PATCH /orders** (status / payment /
  tracking separately) instead of one blob — the trail reads like a story of
  the order's lifecycle.
- **`admin_id` nullable + ON DELETE SET NULL** so deleting a user never breaks
  the historical trail.

## Session 24 — 2026-09-21 — B5.4 granular staff roles (spec BE-04)

**Done**
- `ROLE_DDL` (autocommit, idempotent): `app_role` enum + `super_admin`/`order_manager`/`support`; legacy `admin` keeps full staff access (Rule 4).
- `app/services/roles.py`: `ROLE_CAPABILITIES` capability map + `resolve_roles`/`resolve_role`.
- `app/auth.py`: `AuthUser.roles` (set), `require_staff(capability)` factory, `Staff*` aliases; corrected `require_admin` docstring.
- Per-route guards swapped in: orders (orders/refunds), admin (stats/users/audit/orders/refunds), contact (inbox), coupons, products (catalog), reviews.
- `PUT /admin/users/{id}/roles` — full-replacement role set, admin-only, audited (`update_user_roles` + `user` entity type) — closes B5.1's "role changes not auditable" open item.
- `seed_auth.py`: demo staff `ordermgr@sande.local` / `support@sande.local` (`staff1234`).
- Frontend `auth.tsx`: admin shell accepts all staff roles (per-tab gating stays F4.2).

**Verification** — pytest 39 passed; ruff clean; live smoke **156 checks, 0 failed** (self-grant 403, grant → capability matrix asserted, support blocked from fulfillment but reaching inbox, audit trail shows old/new roles, demote → 403); tsc + vite build clean.

**Not done / open** — F4.2 per-tab UI gating; `super_admin` has no unique power yet (tiers into B5.1b); no role-list endpoint (users list carries roles).

**Decisions** — capability matrix is ours (spec names roles only): order_manager owns fulfillment/refunds/catalog/coupons; support owns inbox/reviews/stats; users/audit admin-only. `storage` stays on coarse `AdminUser` (upload surface, tightened later if needed).

## Session 25 — 2026-09-21 — F4.2 admin shell + per-tab role gating (spec FE-01)

**Done**
- `admin.tsx` rewritten from the tab bar to the [FE-01] shell: sticky blurred topbar (quick search → `/shop?q=`, Persian role badge, logout), right `w-64` sidebar (rounded card on desktop, right-side Sheet on mobile), 18px lucide icons with active terracotta tint, «بازگشت به فروشگاه» link.
- Per-tab role gating (`ROLE_TAB_KEYS`) mirroring backend `ROLE_CAPABILITIES` from B5.4: admin/super_admin → all 8 tabs; order_manager → + fulfillment/catalog; support → dashboard/messages/reviews; unknown roles degrade safely. API stays the authority — this is navigation, not security.
- Live badges on سفارش‌ها (pending+processing) and بازپرداخت‌ها (pending) from `adminKpis("all")`, Persian digits, 60s refetch, 403-tolerant.
- Gate flash fixed (render nothing while auth `loading`).

**Verification** — tsc clean; vite build passes; live role matrix re-checked (support: orders 403/inbox 200/kpis 200; order_manager: 200/200/200 — the UI matrix matches API enforcement exactly).

**Not done / open** — topbar breadcrumbs; `Cmd+K` command palette (input navigates to shop search; needs `command` primitive); admin avatar; route-level `beforeLoad` guards for direct URL access to hidden tabs (data calls 403 gracefully today).

**Decisions** — sidebar styled as a rounded-border card per repo B0.4 widget conventions instead of the spec's hard `border-l` rail; messages/reviews tabs added to the spec's nav list since those routes now exist.

## Session 26 — 2026-09-21 — F4.4 order detail drawer + invoice printing (spec FE-05)

**Done**
- New `components/admin/OrderDetailDrawer.tsx`: left Sheet with the 4-step fulfilment stepper (terracotta circles, advance button over the live `pending → processing → shipped → delivered` lifecycle), receiver box with «کپی آدرس گیرنده» + method, itemised breakdown with `resolveImageUrls`-signed thumbnails and totals, tracking input (F2.8), «لغو سفارش».
- Invoice printing: «چاپ فاکتور رسمی» — the invoice DOM portals to `#__se_invoice_root` on `<body>`; the new `styles.css` `@media print` block hides the app while `body[data-order-print-open]` is set and prints only the A4 invoice (`@page A4; margin: 14mm`, no nav/buttons/backgrounds). Portal + attribute exist only while the drawer is open, so normal printing elsewhere is unaffected.
- `admin.orders.tsx`: per-order «مشاهده و پردازش» opens the drawer; drawer's order object re-resolved from the refetched list (never stale); invalidation now covers the KPI queries.

**Verification** — tsc clean; vite build passes; live endpoints all already smoke-covered (156 checks). Manual: stepper advance, address copy, tracking save/clear, print preview shows only the invoice.

**Not done / open** — payment-status toggle inside the drawer (list select still the tool); tax/company-registration fields on the invoice (no data model); A5 variant; print type scale.

**Decisions** — stepper labels mapped to the live lifecycle instead of the spec's «تأیید پرداخت» wording (Rule 4: status strings untouchable); pending can advance while unpaid (status/payment independent, as elsewhere); invoice portalled to body rather than hidden-by-CSS-in-place (reliable across Radix overlays).

## Session 27 — 2026-09-21 — B6.1 order state machine + F4.5 coupons manager

**Done**
- B6.1 (spec BE-05): `app/services/order_lifecycle.py` — `ALLOWED_STATUS_TRANSITIONS` (pending→processing→shipped→delivered, cancel from pending/processing, terminal delivered/cancelled), `assert_transition` (409 with Persian message on illegal PATCH), `cancel_order_tx` used by BOTH cancel endpoints (POST /cancel and PATCH status=cancelled — the admin dropdown offers «لغو شده»), `restore_stock` mirroring checkout's decrement order (variants via information_schema column check, then product aggregate; products.id is TEXT so raw equality). Smoke: illegal skips 409, legal advance 200, cancel restores stock (+1), cancelled cannot revive.
- F4.5 (spec FE-07): `/admin/coupons` manager — filter chips, ticket cards with notches + copy code + Switch active toggle + usage progress (red at 100%), create/edit dialog (percent XOR amount like the backend), delete, code generator. `api.ts` AdminCoupon type + 5 client methods. New backend `DELETE /coupons/{id}` (audited `delete_coupon`) — the CRUD had no delete; generate is POST (client initially GET, caught live).

**Verification** — pytest 39 passed; ruff clean; live smoke 151 checks 0 failed (state-machine block asserts the full transition flow); tsc clean; vite build passes; coupon CRUD verified live (list/create/patch/delete/generate/401).

**Bugs found & fixed during verification** — order_items.variant_id may not exist on older stacks (information_schema guard); products.id is TEXT not UUID (CAST broke restore); smoke's checkout section only accepted 201 while the API returns 200 (order ids fell through, second-order section silently skipped); smoke now uses a second fresh order so payment-complete's processing advance doesn't skew the machine tests.

**Not done / open** — B4.9 stock reservation TTL; DB-level status trigger (API-only enforcement, noted for B5.1b); Persian Jalali date-picker component (native input used; needs a dependency decision); bulk code generation.

**Decisions** — same-status PATCH writes stay legal (idempotent); cancel semantics unified across both endpoints so the UI dropdown and the API can't diverge; seed stock top-up command documented in the audit for repeat smoke runs.

## Session 28 — 2026-09-21 — B5.1a audit IP capture + F4.1 status badges

**Done**
- B5.1a: `audit.client_ip_ctx` contextvar + `capture_client_ip` middleware in main.py (XFF first hop trusted — backend always sits behind the compose proxy/loopback — else socket peer); `record_audit` falls back to the context when no explicit ip is passed, so all 17 audit sites now record IPs with zero signature changes. Live-verified with `X-Forwarded-For: 198.51.100.7` landing in audit_logs; smoke asserts entries carry IPs.
- F4.1: new `components/StatusBadge.tsx` per DESIGN_SYSTEM §7.2 — tones positive/progress/waiting/negative/meta from the §2.3 token recipes (no raw palette classes), label always names the status, `title` keeps the Latin value, unknown → meta. Converted: account.orders (was terracotta/sand pair), admin.refunds (3-way ternary chip), admin.index latest orders, OrderDetailDrawer header chips. Extended tone map with succeeded/failed/new (payments + contact inbox).

**Verification** — pytest 39 passed; ruff clean; live smoke **152 checks, 0 failed** (incl. the new IP assertion); tsc clean; vite build passes.

**Not done / open** — B5.1b DB tamper-resistance (needs an app-role decision: single-role user would REVOKE itself out); no trusted-proxy allowlist for XFF (fine for this stack, revisit if ever exposed directly).

**Decisions** — middleware + contextvar over threading `Request` through every router (zero churn at 17 call sites, works for service-layer writes too); unknown statuses render as brand tone rather than erroring (forward compatibility with future statuses).

## Session 29 — 2026-09-22 — F2.5 pagination everywhere

**Done:** envelope pagination (`{items,total,page,page_size,pages}`; bare list
without `?page=` for compatibility) via new `services/pagination.py` on
`/products`, `/orders`, `/admin/orders|users|payments|contact-messages|reviews`;
`offset` on `/admin/audit-logs`. New shared `Pager` component (Persian digits,
terracotta active, RTL, hidden at ≤1 page) wired into shop (`?page=` URL param,
12/page), admin orders/users/messages/reviews (20/page) and account orders
(10/page). api.ts gained `Page<T>`, `toPage()` and page params on the affected
clients.

**Bug found by the smoke's own traffic:** `_optional_admin` in
`routers/products.py` fed `resolve_role()` (string) into `AuthUser.roles`
(set) — every authenticated `/products` call 500'd since B5.4. Fixed to
`resolve_roles()`.

**Verification:** pytest 39 passed · ruff clean · smoke **170 checks, 0 failed**
(new F2.5 section) · tsc clean · vite build passes (needs Node ≥22 locally:
`PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"` — Vite 8's `styleText`
requirement; Node 20.9 is the default here).

**Not done:** no admin payments screen (client method paged anyway); audit-log
UI stays limit/offset; infinite-scroll not wanted. Details:
`plan/audit/2026-09-22-f25-pagination-everywhere.md`.

## Session 29b — 2026-09-22 — B2.2 reports & exports (BE-08)

**Done:** new `/admin/export/orders.{csv,xlsx}`, `/admin/export/products.{csv,xlsx}`
and `/admin/export/report` (daily/monthly revenue excluding cancelled + top-10
best-sellers), all under the `StaffOrders` capability guard. CSV via stdlib
(RFC-4180), XLSX via openpyxl (added to pyproject, image rebuilt), Persian
filenames in `filename*`. Order rows carry customer + address + item
breakdown + subtotal/discount/shipping/total.

**Caught during verification:** `:status::text` casts break asyncpg's bind
parser (syntax error at ":") → `CAST(:status AS text)`; container needed a
rebuild since deps are baked while code is volume-mounted.

**Not done:** CSV product import (needs overwrite-policy decision → new B2.2a
checkbox), export buttons in the UI (deferred to the F4.3 data-grid toolbar),
PDF invoices (B2.3 open). Details:
`plan/audit/2026-09-22-b22-reports-exports.md`.

**Verification:** pytest 39 passed · ruff clean · smoke **186 checks, 0 failed**.

## Session 29c — 2026-09-22 — B2.4 co-purchase recommendations

**Done:** `co_purchases(product_a, product_b, votes)` pair table (canonical
`a < b` pairs, DDL + first refresh in startup) recomputed inside the checkout
transaction whenever a cart has ≥2 lines. `/products/{id}/recommendations`
now blends learned votes (×3) with the existing category/popularity heuristic
(same payload shape, `/related` untouched, self always excluded).

**Bugs en route:** referenced `p.review_count` (an alias in `_PRODUCT_COLS`,
not a column) and appended a second FROM to `_SELECT` — both 500s caught by
the smoke, fixed by composing the query from `_PRODUCT_COLS` + a score
expression.

**Verification:** pytest 39 passed · ruff clean · smoke **189 checks, 0 failed**
(first cart made 2-line so the engine is exercised; post-checkout
recommendations 200). Live: `set-18|tshirt-4 votes=2`; recommendations for
`set-18` rank co-purchased `set-17` first. Details:
`plan/audit/2026-09-22-b24-co-purchase-recommendations.md`.

## Session 30 — 2026-09-22 — Full end-to-end audit (backend + frontend) and fixes

**Done**
- Stood the project up from nothing on a clean host: backend venv + dev deps, `infra/.env` (MinIO moved to 9010/9011 — 9000/9001 were taken), full `docker compose up --build`, Playwright/Chromium for the browser passes. Baseline recorded before any change: pytest 39 passed, ruff clean, `tsc` clean, `bun run build` OK, `bun run lint` **failing** (45 prettier errors), and `db-init` **exiting 1** on a clean volume.
- Fixed two P0s: (1) `db-init` died in `seed_auth` on the `order_manager` enum value because the additive `ROLE_DDL` only ran if the API container booted first — the seeds now run `startup_ddl()` themselves, so products/demo/coupons stop being skipped; (2) `GET /products` returned **500 for every authenticated caller** (`_optional_admin` passed a role string where a role set was expected), which broke the cart for signed-in shoppers — every line rendered as «محصول حذف‌شده» with a ۰ تومان total. The duplicate dependency was deleted in favour of the shared `OptionalUser`.
- Fixed two P1s: the payment simulator (`POST /orders/{id}/payment-complete`) let a customer mark their own order paid regardless of gateway configuration — now simulation-mode only; and re-settling an already-`refunded` request inserted a **second** refund payment row — settlement is now terminal.
- Implemented the two `[BE-05]` requirements that were missing: an order status state machine (cancelled/delivered terminal; `cancelled → shipped` is now 409) and stock restoration on cancellation, guarded so a repeated cancel cannot inflate stock.
- Hardening + consistency: no staff role from a stale JWT claim (a demoted admin kept access for up to 7 days); `POST /payments/verify` scoped to the session owner; `GET /orders/{id}` readable by staff as its docstring always claimed; coupon codes normalised at redemption so a code `validate` accepted is not rejected at checkout.
- Frontend: per-route role guard in the admin shell (`[FE-01]`.3), Persian 404/error pages (B1.4), real staff role labels in `/admin/users`, and `bun run lint` back to zero errors.

**Explicitly not done**
- Unimplemented backlog features were left alone (coupons manager `[FE-07]`, role-change UI/LTV `[FE-08]`, SMS `[BE-07]`, exports `[BE-08]`, reusable grid `[FE-02]`, audit-log UI) — they are backlog, not regressions, and are now checkboxes.
- Per-variant stock restoration (needs `order_items.variant_id`), the bare `except Exception` in refund creation, pagination for `/products` and `/admin/orders`, and the bundle/duplicate-fetch performance items were reported, not changed.
- No README/FEATURES/DESIGN_SYSTEM edits: nothing about endpoints, setup, scripts, features or tokens changed — the fixes restored documented behaviour.

**Verification** — pytest 39 passed; ruff clean; `tests/api_smoke.py` 173 checks, 0 failed; `tsc` clean; `bun run lint` 0 errors (14 pre-existing warnings); `bun run build` OK; clean-volume `docker compose down -v && up --build` seeds all four stages with `db-init` exiting 0; browser regression (headless Chromium) of the full purchase flow through the simulated gateway to a paid order, admin panel, role gating and 375→1920 responsive sweep — no 5xx and no page errors.

**Decisions** — the state machine is expressed in the existing status vocabulary (Rule 4: no string changed); the `admin` legacy role keeps full staff access; the broken `_optional_admin` was deleted rather than repaired, since `app/auth.py` already had the correct dependency.

## Session 31 — 2026-09-22 — Run the stack + optional mock dataset

**Done**
- Brought the full compose stack up from an empty volume (the audit's `db-init` fix holds: exit 0, all four seed stages) and confirmed the storefront, API and admin panel serve.
- New `backend/app/seed_mock.py`: an **optional**, idempotent, deterministic demo dataset (fixed RNG seed, so a fresh database always produces the same figures). 8 customers with weekly-staggered registration dates, 31 orders backdated over 47 days across every status/payment combination, refund claims in all four `[BE-03]` states, 18 reviews written only by people who actually received the product, a size × colour variant matrix, a 5-message inbox and 4 campaign coupons (one exhausted, one expired). Money, stock and payment/refund ledger rows are internally consistent — verified with SQL invariants (item sums, totals, the ۸۹٬۰۰۰/۲٬۰۰۰٬۰۰۰ shipping rule, payment presence, tracking only after dispatch, no negative stock, no orphans): all zero violations.
- Fixed a **pre-existing** bug in `tests/api_smoke.py` that this work exposed: the "audit log records the admin order mutation" assertion ran 41 lines before the script's first `PATCH /orders/{id}`, so it only ever passed on a database left dirty by a previous run. Reproduced on a clean database both with and without the mock data; the block was moved after the mutations rather than the assertion weakened.
- Documented the optional seed in `backend/README.md` and `infra/README.md`.

**Explicitly not done**
- `seed_mock` was deliberately **not** added to the compose `db-init` chain — the default stack stays the small starter dataset.
- No search-history / recently-viewed rows (per-session personalisation reads wrong when backdated).
- No frontend or product-code changes in this session.

**Verification** — pytest 39 passed; ruff clean; `tests/api_smoke.py` 173 checks / 0 failed on a *first* run against a clean database (with and without mock data — it used to fail there); double-run of `seed_mock` is a no-op with unchanged counts; browser check as admin confirmed the dashboard KPIs/trend/donut, 33 order cards on `/admin/orders`, refund tabs at 3 pending / 2 settled / 5 all, and populated inventory, inbox, reviews and users screens, with no failed API calls and no page errors.

**Decisions** — deterministic RNG over random data so demos are reproducible; a marker account as the idempotency guard rather than per-table counts; cancelled orders never take stock, matching the restore-on-cancel rule fixed earlier in the day.

## Session 32 — 2026-09-22 — Agent guardrail rules (Rules 6–15)

**Done**
- Read `AGENTS.md`, `plan/RULES.md`, the dev spec, `backend/pyproject.toml`, `vogue-vintage-vibes/package.json`, `infra/docker-compose.yml`, `infra/initdb/`, the backend routers/services/tests, `src/lib/` and the 2026-09-22 full-stack audit before writing anything.
- Split `plan/RULES.md` into **Part A — process rules (0–5, unchanged)** and **Part B — engineering rules (6–15, new)**, with a scope note exempting markdown-only tasks and a global stop condition ("if you cannot answer from the repo, inspect — do not guess").
- New Rules: 6 reconnaissance + blast radius · 7 one canonical implementation (with a table of canonical homes: `app/auth.py`, `services/roles.py`, `services/pricing.py`, `services/order_lifecycle.py`, `services/payments.py`, `src/lib/api.ts`, …) · 8 contract-first across the boundary · 9 security before the happy path (multi-actor + direct-URL testing) · 10 statuses are state machines and repeats must be safe · 11 money/inventory invariants with a mandatory test · 12 minimal diff · 13 verify narrow→wide incl. error paths, never weaken validation · 14 clean-environment verification for infra/DB/seed/config · 15 document what actually happened, with named verification levels.
- Each new rule is traced in the audit to a specific defect the 2026-09-22 full-stack audit found while Rules 0–5 were already in force.
- `AGENTS.md` gained one concise always-loaded section (one bullet per rule, pointing at `plan/RULES.md`); `plan/README.md`'s short-rule list was extended to match.
- Audit: [`plan/audit/2026-09-22-agent-guardrail-rules.md`](./audit/2026-09-22-agent-guardrail-rules.md).

**Explicitly not done**
- No application code, tests, infra files or `design/SANDE_FULL_DEV_SPEC.md` changed; no task checkbox ticked and no feature marked complete (user instruction).
- No test/lint/Docker/browser run — a markdown-only change, and no verification beyond a documentation review is claimed.
- The stale Part C backlog rows in the dev spec (refunds UI, coupons manager, order drawer) were left alone; the spec is the user's document.
- READMEs, `FEATURES.md`, `feature-roadmap.md` and `DESIGN_SYSTEM.md` untouched — no endpoint, script, stack, feature or UI convention changed.

**Decisions** — detail lives only in `plan/RULES.md`, `AGENTS.md` keeps a one-bullet-per-rule summary, so the always-loaded file stays short; the user's twenty proposed guardrails were merged down to ten rules (consumers→Rule 6, idempotency→Rule 10, direct-URL/API→Rule 9, dirty environments→Rule 14, fake tests / weakened validation / error paths→Rule 13, implemented-vs-verified→Rule 15) to avoid redundant rules; Rules 0–5 were kept verbatim and Rule 4's protected status strings and money rules are restated by Rules 10/11, never altered.

---

## Session — 2026-09-22 — Full backlog and architecture audit (all four task/spec documents)

**Task** — ad-hoc user request: establish the real remaining implementation backlog by
cross-checking the live codebase against `plan/backend-tasks.md`,
`plan/frontend-tasks.md`, `plan/ADMIN-BACKEND_TASKS.md` and
`plan/ADMIN-FRONTEND_TASKS.md`, then record one authoritative prioritized backlog for a
downstream agent to execute from. Audit only — explicitly **no** implementation.

**Spec check (Rule 0)** — `design/SANDE_FULL_DEV_SPEC.md` read first. Its `[BE-01]`…
`[BE-09]` and `[FE-01]`…`[FE-08]` blocks were used as the requirement set that the two
ADMIN documents restate, and every requirement was mapped to a live implementation or to
a new proposed task. The spec's stack header and the ADMIN files' Supabase / RLS / RPC /
`createServerFn` wording were **not** followed (Rule 0.2 — the live FastAPI + own-JWT +
MinIO repo wins) and are recorded as `STALE`/`SUPERSEDED` instead. No Rule-4 status
string or cart money rule was touched or proposed for change.

**What was done** — 135 tracked checkboxes classified against the source
(DONE/PARTIAL/TODO/BLOCKED/OBSOLETE/DUPLICATE/UNCLEAR) with a file-path or endpoint
citation each; the two ADMIN specs converted into an executable backlog with 13 of their
17 blocks mapped onto existing tasks and only 9 genuinely new tasks proposed
(`AB-BE-01..03`, `AB-FE-01..06`); nine product/architecture decisions (D1–D9) separated
out; 14 documentation-drift items recorded; a dependency graph and a five-phase
implementation order derived. Result: 118 done, 4 partial, 11 todo, 7 blocked, 1
obsolete, 2 duplicate → **24 actionable items**.

**Headline finding (P0)** — `backend/app/services/order_lifecycle.py::restore_stock`
documents and contains a per-variant stock restore branch that can never execute:
`order_items` has no `variant_id` column (`infra/initdb/02-public-schema.sql:107-118`,
no additive DDL in `app/db.py`) and `services/checkout.py:180-198` never writes one,
while `checkout.py:226-232` *does* decrement `product_variants.stock`. Every cancellation
of a variant order therefore destroys that combination's inventory, silently and
permanently. Tracked as the existing open checkbox **B6.8**, whose severity the task text
understates. Established from the schema and the INSERT statement; **not** reproduced at
runtime in this session.

**What was explicitly NOT done** — no production code, no task file, no checkbox, no
rule file and no spec was modified, per the user's instruction. In particular `B6.10`
(found already implemented by F2.5) and `B2.6` (obsolete by its own text) were left
unticked and unstruck, and the duplicate `B6.1` ID collision with `B6.3` was left in
place; all three are recorded under Documentation Drift for a deliberate follow-up.
Nothing was executed — no `pytest`, `ruff`, `api_smoke.py`, `bun run lint/build` or
Docker run — so every status is *inspected*, not *verified* (Rule 15), except where a
prior audit file is cited by name. READMEs, `FEATURES.md`, `DESIGN_SYSTEM.md`,
`feature-roadmap.md` and `plan/README.md` were left untouched: no endpoint, setup step,
script, stack, feature or design token changed.

**Decisions taken** — (1) the two ADMIN files are treated as *specifications*, not
tracked task lists, since they carry no checkboxes or audit links and counting their
headings would inflate the backlog; the mapping table in §9.1 of the audit is the bridge.
(2) `AB-FE-02` (export UI) was split out rather than left inside `F4.3`, because
`B2.2`'s note parks a finished, guarded backend export feature behind the undecided
`@tanstack/react-table` install (D8) — which is why it has shipped nowhere. (3) The
`[FE-05]` stepper-label deviation and the `[BE-09]` "< 5 units" mismatch were recorded as
*correct* deviations rather than defects, so a future agent does not "fix" them back into
a Rule-4 violation or a regression. (4) No task was created for `[FE-06]`'s IBAN/Sheba
panel: it stores new PII and needs decision D6 first.

→ audit: [2026-09-22-full-backlog-audit.md](audit/2026-09-22-full-backlog-audit.md)

---

## 2026-09-22 — B6.8 per-variant stock restoration on cancellation

**Task** — `B6.8` (P0, Master Backlog batch A), executed alone from
`plan/MASTER-BACKLOG.md`.

**What was done** — `order_items` now carries a `variant_id` column, added
idempotently in `CATALOG_DDL` (`backend/app/db.py`) right after the
`product_variants` table it references, with `ON DELETE SET NULL` so removing a
variant never destroys order history. `services/checkout.py` writes the
already-resolved variant id onto each order line; the restore path in
`services/order_lifecycle.py` was left untouched because it was *already*
variant-aware — the column it read simply never existed, so its
`information_schema` guard always fell back to aggregate-only. Cancellation now
returns stock to the variant row and the product aggregate inside one
transaction, on both entry points (`POST /orders/{id}/cancel` and an admin
`PATCH /orders/{id}` to `cancelled`). New DB-backed test module
`backend/tests/test_order_lifecycle_stock.py` covers the four acceptance tests
plus the persisted-id case; it skips when no database is reachable so the
pure-unit suite still runs anywhere.

**Tests run** — `pytest -q tests/test_order_lifecycle_stock.py` (5 passed),
full `pytest -q` (44 passed), `ruff check app tests` (clean),
`tests/api_smoke.py` against the running stack (196 checks, 0 failed),
`docker compose down -v && up -d --build` with `db-init` exiting 0 through all
four seed stages and `/health` responding, and a live HTTP checkout → cancel →
repeat-cancel flow on a freshly created variant (stocks 25/6 → 23/4 → 25/6 →
25/6), including the no-variant line and the admin PATCH path (repeat → 409).
A mutation check (binding `variant_id` back to `None`) failed three of the five
new tests, proving they cover the defect.

**Verification level** — *fully verified*.

**What was explicitly NOT done** — historical `order_items` rows are not
backfilled with a guessed `variant_id` (the matrix may have changed since, so a
`(product_id, size, color)` re-match would be a guess); the `[BE-01]`
`inventory_logs` ledger stays with `AB-BE-01`; the redundant
`information_schema` probe in `restore_stock()` was left in place under Rule 12
and recorded as `NEW-B68-1` / `B6.8a` instead. `FEATURES.md`,
`DESIGN_SYSTEM.md`, `feature-roadmap.md`, `plan/README.md` and `infra/README.md`
were left untouched: no endpoint, UI, feature status, design token or infra step
changed. `backend/README.md` was updated (stock model + catalog DDL list).

**Decisions taken** — (1) the DDL went into `CATALOG_DDL` rather than a new
block, because that list already owns `product_variants` and every seed module
calls `startup_ddl()`, satisfying the backlog's "seed jobs can independently
apply the DDL" requirement with no new code. (2) The new tests talk to a real
Postgres instead of mocking, because the invariant lives in SQL; they skip
rather than fail without one. (3) `order_lifecycle.py` was deliberately not
touched, keeping the diff to the two places that were actually wrong.

→ audit: [2026-09-22-b68-variant-stock-restore.md](audit/2026-09-22-b68-variant-stock-restore.md)

**Next backlog pointer** — `B6.9` (narrow refund exception handling).

---

## 2026-09-22 — B6.9 narrow refund exception handling

**Task** — `B6.9` (P1, Master Backlog batch A), executed alone after B6.8.

**What was done** — `POST /orders/{id}/refunds` wrapped its INSERT in a bare
`except Exception`, so any failure — a dropped connection, a bug in the handler,
a foreign-key violation — was answered with the 409 «برای این سفارش قبلاً
درخواست بازپرداخت ثبت شده است». The handler now catches `IntegrityError`
(following the existing `routers/auth.py::signup` pattern) and returns that 409
**only** for Postgres SQLSTATE `23505` (`unique_violation`, which is the real
`UNIQUE (order_id)` duplicate); anything else is rolled back, logged with a
traceback and re-raised. A four-line module-private `_is_unique_violation()`
sits next to its single caller. Success and duplicate responses are
byte-identical to before, so no frontend change was needed.

**Tests run** — new `backend/tests/test_refund_requests.py` (10 passed: four
SQLSTATE predicate unit tests, plus DB-backed endpoint tests for the 201 success,
the true duplicate leaving exactly one row, an injected `23503` failure
surfacing as 500 rather than a false 409, the not-cancelled/not-paid 409, a
wrong-owner 404 and an anonymous 401); full `pytest -q` (54 passed);
`ruff check app tests` clean; `tests/api_smoke.py` 196 checks / 0 failed against
the rebuilt container; and a live HTTP flow (checkout → payment-complete →
cancel → refund 201 → repeat 409 → anonymous 401 → unknown order 404) with no
traceback in `docker compose logs backend`. A mutation check (restoring the bare
`except Exception`) turns exactly the unrelated-failure test red.

**Verification level** — *integration tested*, plus real-HTTP exercise. Rule 14
clean-environment verification was deliberately not repeated: this task changes
no DDL, seed, Docker or configuration file, and B6.8's `down -v` proof earlier
today still describes the schema.

**What was explicitly NOT done** — the unexpected-failure path returns FastAPI's
generic 500 body rather than a Persian message (intended: a fault must not
impersonate a business condition). `api_smoke.py` was not extended with a
duplicate-refund check, to keep the diff to the one handler. The same broad
`except Exception` → 409 shape still exists in `routers/products.py` (four CRUD
handlers) and `routers/storage.py`; it was recorded as `NEW-B69-1` / `B6.9a`
instead of being fixed here (Rule 12). No README, FEATURES, DESIGN_SYSTEM,
roadmap or plan/README change was needed — no endpoint, setup step, script,
stack or UI convention moved.

**Decisions taken** — (1) two narrowings rather than one: `Exception` →
`IntegrityError` → SQLSTATE `23505`, because a foreign-key or check violation on
`refund_requests` is a defect and must not be disguised as a duplicate either.
(2) The predicate stayed module-private instead of becoming a shared service
helper — one caller today; it should move if `NEW-B69-1` gives it more.
(3) The unrelated-failure test injects the error through a `get_session`
dependency override rather than mocking the router, so the real handler code
runs.

→ audit: [2026-09-22-b69-refund-exception-handling.md](audit/2026-09-22-b69-refund-exception-handling.md)

**Next backlog pointer** — `AB-BE-03` (coupon max discount cap).

---

## 2026-09-22 — AB-BE-03 coupon max discount cap

**Task** — `AB-BE-03` (P1, Master Backlog batch A, source ADMIN-BACKEND
`[BE-02]`), executed alone after B6.9. It completes batch A.

**What was done** — a percent-off coupon had no ceiling, so a large cart
discounted without limit. `coupons` gains a nullable
`max_discount_cap INTEGER CHECK (… > 0)` through `COUPON_DDL`, and the clamp
lives in `app/services/coupons.py::compute_discount` — the single function both
`POST /coupons/validate` and checkout reach via `validate_coupon`, so the quote
the cart shows and the discount the order stores can never disagree. The cap
applies to **percent-off coupons only**: a fixed `amount_off` is already a stated
ceiling in tomans. NULL means uncapped, so `SANDE10`, `WELCOME500` and every
other existing coupon behave exactly as before. The field is exposed in
`CouponOut` / `CouponCreate` / `CouponUpdate`, in the admin list, in the
create-audit entry, and can be cleared by PATCHing `0` (the same sentinel
convention `expires_at: ""` already uses). `models.py` gained the column and
`backend/README.md` documents it.

**Tests run** — `TestMaxDiscountCap` in `tests/test_pricing_and_coupons.py`
(9 cases: under/over/at the cap, no cap, fixed amount ignoring it, cap larger
than the subtotal, `validate_coupon` agreeing, and the cap not bypassing the
`min_subtotal` or `max_uses` rules) and a new DB-backed
`tests/test_coupon_cap_integration.py` (7 cases: validate returns the capped
amount and the cap; checkout stores the identical amount in the quote,
`orders.discount`, `orders.total` and `coupon_redemptions.amount`; NULL cap keeps
the full percentage; a small cart is not clamped; admin create→list→patch→clear
round-trip; negative cap 422; customer 403). Full `pytest -q` 70 passed; ruff
clean; `api_smoke.py` 196/0; clean-environment `docker compose down -v &&
up -d --build` with `db-init` exit 0, the column and its CHECK present on a
fresh database and the seeded coupons NULL-capped; plus a live HTTP flow where a
50% coupon capped at 300,000 discounted a 5,670,000 cart by exactly 300,000 at
both validate (lowercase code) and checkout, while `SANDE10` and `WELCOME500`
were unaffected. Mutation check: deleting the three clamp lines reddens exactly
four tests.

**Verification level** — *fully verified*.

**What was explicitly NOT done** — no admin UI field: `admin.coupons.tsx` and the
`AdminCoupon` / `adminCreateCoupon` / `adminUpdateCoupon` types in
`src/lib/api.ts` are untouched, so the ceiling is API-only for now. AB-BE-03's
layer is `backend_db_pricing` and the full-backlog audit listed the dialog field
as a frontend dependency, so it was recorded as `NEW-ABBE03-1` / `F5.9` instead.
Fixed `amount_off` coupons stay uncapped by design. `CouponUpdate` still cannot
clear `max_uses` or `min_subtotal` (pre-existing convention, left alone).
`feature-roadmap.md`, `FEATURES.md`, `DESIGN_SYSTEM.md`, `infra/README.md`,
`vogue-vintage-vibes/README.md` and `plan/README.md` were left untouched — the
capability is not user-visible until the dialog field ships.

**Decisions taken** — (1) the clamp went into `compute_discount`, **not** into
`app/services/pricing.py` as the 2026-09-22 full-backlog audit proposed:
`quote()` receives an already computed integer discount and knows nothing about
coupons, so clamping there would have required a second copy for the validate
endpoint — the two-sources-of-truth Rule 7 forbids. The deviation is recorded in
the audit. (2) `INTEGER` tomans, not the spec's `NUMERIC`, because every money
column in this repo is an integer. (3) `0` on PATCH clears the ceiling rather
than adding a separate `clear_max_discount_cap` flag.

→ audit: [2026-09-22-abbe03-coupon-max-discount-cap.md](audit/2026-09-22-abbe03-coupon-max-discount-cap.md)

**Next backlog pointer** — `F5.5` (audit-log viewer) — batch A is complete.

## 2026-09-22 — Backlog ID normalization (F5.9) + F5.5 audit-log viewer

**Backlog normalization (markdown only)** — the task discovered during AB-BE-03
is now executed under its official ID: the Master Backlog JSON entry
`NEW-ABBE03-1` became `F5.9` (`discovered_as: "NEW-ABBE03-1"`,
`discovered_during: "AB-BE-03"`; P2 / TODO / depends on AB-BE-03 / batch B
unchanged), a matching `## F5.9` prose section was added under P2 in line with
`frontend-tasks.md` F5.9, and the Batch B list, dependency graph, AB-BE-03
"not delivered" line and reconciliation record now say `F5.9`. JSON parsed
cleanly; no executable `NEW-ABBE03-1` remains; no duplicate task; the pointer
stayed on F5.5.

**F5.5 — done.** New `/admin/audit` route (`admin.audit.tsx`) over the existing
`GET /admin/audit-logs` contract (bare array, `limit`/`offset`, no total):
action / entity / staff / entity-id filters, 25-row paging that asks for 26
rows to learn whether a next page exists, Jalali timestamp with time
(`formatFaDateTime`, new in `src/lib/format.ts`), IP, a per-entry old→new value
table, and loading / empty / error states. `api.adminAuditLogs()` +
`AuditLogEntry` / `AuditLogQuery` in `src/lib/api.ts`. The admin shell got an
`audit` tab («گزارش فعالیت‌ها») for `admin` / `super_admin` only, so the existing
`tabAllowed` guard shows the Persian role notice to `order_manager` / `support`
on direct entry. Backend untouched.

**Verification** — `tsc` clean; `bun run lint` 0 errors (15 pre-existing
warnings, none in touched files); `bun run build` OK; backend `pytest -q` 70
passed against the live DB, ruff clean, `api_smoke.py` 196/0; headless-Chromium
script 35/35: anonymous redirect, customer / support / order_manager blocked on
direct URL and refresh with zero audit requests, admin list + filters + paging
+ value table + empty states, mocked 500/403 error states with retry, 375 px
without horizontal scroll. Verification level: *browser tested*. To have two
pages of real data, a throwaway coupon `F55AUDIT` was created, patched 30 times
and deleted through the admin API, which left real audit rows in the dev DB.

**What was explicitly NOT done** — F5.6, F5.9, AB-FE-02, AB-FE-05 and F4.3 were
not touched. The backend defect found during F5.5 (malformed `admin_id` → 500)
was recorded as `B5.1c` (discovered as `NEW-F55-1`, P3, batch C) and not fixed.
No total/page count (the contract has none), filters are not in the URL, and the
Playwright script is not committed. `backend/README.md`, `infra/README.md`,
`vogue-vintage-vibes/README.md` and the spec were left untouched. The Master
Backlog still uses `NEW-B68-1` / `NEW-B69-1` as executable IDs with no prose
sections, although `backend-tasks.md` names them B6.8a / B6.9a. That is the same
normalization gap as F5.9, but outside this session's scope, so it is noted and
not changed.

**Decisions taken** — (1) offset paging with a `limit + 1` probe instead of
changing the endpoint to the `Page<T>` envelope (the user said not to invent a
new audit API). (2) The staff filter is populated from `api.adminUsers()` (same
admin/super_admin capability as the audit log), so only real UUIDs are ever sent
as `admin_id`. (3) The §12 priority table was stale compared with the JSON index,
so it was recomputed (P0 0 / P1 6 / P2 13 / P3 8 = 27), and the JSON `counts`
block was updated to 31 executable / 4 done.

→ audit: [2026-09-22-f55-audit-log-viewer.md](audit/2026-09-22-f55-audit-log-viewer.md)

**Next backlog pointer** — `F5.6` (role management UI).

## 2026-09-22 — F5.6 role management UI

**F5.6 — done.** `/admin/users` rows now have a «نقش‌ها» button, disabled on the
signed-in admin's own row. It opens a two-step dialog, per spec [FE-08]:
checkboxes for `super_admin` / `order_manager` / `support`, each with a
capability summary, with legacy `admin` / `customer` shown read-only. The second
step shows the +/− diff and requires typing the user's email; a full-set PUT then
goes to the existing `PUT /admin/users/{id}/roles`. Success invalidates the users
and audit-log caches. `api.adminSetUserRoles()` + `StaffRole` in `src/lib/api.ts`.
Backend untouched.

**Verification** — tsc clean; lint 0 errors (15 pre-existing warnings); build
OK; backend pytest 70 passed against the live DB, ruff clean, `api_smoke.py`
196/0. Headless Chromium + API script, 40/40:
- the 401/403/403/403/422/404 authority matrix, including order_manager
  self-escalation and a client-sent `admin` role;
- page guards for anonymous, customer, support and order_manager;
- the grant and revoke flows, including the effect on the target's
  already-issued JWT (inbox 200 after grant, 403 after revoke);
- the audit row;
- mocked 403/500 keeping the dialog open;
- 375 px layout.

All seeded roles were restored at the end. The F5.5 script was re-run (35/35)
after making it independent of the audit-log size. Level: *browser tested*.

**Correction to F5.5** — the audit-log error panel used literal `rose-*` classes.
DESIGN_SYSTEM.md §2.3 forbids inline palette classes and maps "negative" to the
`destructive` tokens, so it now uses `border-destructive/30 bg-destructive/10
text-destructive`, and the F5.6 diff uses `text-sage-deep` / `text-destructive`.
The F5.5 audit carries a note.

**What was explicitly NOT done**
- Backend lockout guard: the endpoint accepts self-demotion and removal of the
  last `super_admin`. Recorded as `B5.4a` (discovered as `NEW-F56-1`, P2) and not
  fixed. The UI's own-row block is UX only.
- Customer sidebar: a customer on `/admin/*` sees support tabs next to the
  no-access notice. Recorded as `F5.10` (discovered as `NEW-F56-2`, P3). This is
  pre-existing.
- Palette classes in `admin.refunds.tsx` / `admin.index.tsx`: pre-existing, not
  touched.
- Other tasks not started: F5.9, AB-FE-02, AB-FE-05, F4.3 and the rest of
  [FE-08] (AB-FE-06).
- Docs left untouched: `backend/README.md`, `infra/README.md`,
  `vogue-vintage-vibes/README.md` and the spec.

**Decisions taken**
1. The typed confirmation token is the account email, the login identity, with
   the user id as fallback. The check ignores case and surrounding spaces.
2. The editor is blocked on your own row instead of adding a backend guard, which
   is logged as B5.4a.
3. The legacy `admin` role is read-only in the UI because the endpoint cannot set
   it.
4. The repo's DESIGN_SYSTEM token rules take precedence over the spec's literal
   palette classes.

→ audit: [2026-09-22-f56-role-management-ui.md](audit/2026-09-22-f56-role-management-ui.md)

**Next backlog pointer** — `AB-FE-02` (admin export controls; don't run it in
parallel with AB-FE-05 because both edit `admin.products.tsx`).

## 2026-09-22 — AB-FE-02 admin export controls

**AB-FE-02 — done.** B2.2's exports now have a UI:
- `/admin/orders` has an export panel. Pick a local date range (both days
  inclusive, default the last 30 days) and an order status, then «خروجی CSV» /
  «خروجی Excel». A Jalali preview shows the chosen range, and a collapsible
  «گزارش فروش همین بازه» shows best-sellers and daily rows from
  `/admin/export/report`.
- `/admin/products` has catalog CSV/Excel buttons.
- Files download through a new `api.ts::requestFile()`: bearer token, the same
  `ApiError`, and the server's RFC-6266 Persian filename. It shares
  `authHeaders` / `parseBody` / `apiError`, which were extracted from `request()`
  without changing its behaviour.
- New component `components/admin/ExportControls.tsx`.
- One backend line: CORS `expose_headers=["Content-Disposition"]`. The browser
  cannot read the filename cross-origin otherwise. Covered by the new
  `tests/test_cors_expose.py`.

**Contract quirks handled in the UI** — `to` is exclusive and `parse_range` drops
any UTC offset, so `exportRange()` sends local midnight of `from` and of the day
after `to` as offset-less UTC. Chromium turns the Persian ZWNJ in the server
filename into `_`, so the saved name uses a space instead.

**Verification**
- Backend: pytest 72 passed against the live DB (2 new tests; the positive one
  fails without the change); ruff clean; `api_smoke.py` 196/0.
- Frontend: tsc clean; lint 0 errors; build OK.
- Headless Chromium in Asia/Tehran with real downloads: 45/45 (run twice). The
  first run was 44/45 because of the ZWNJ, fixed as above.
- F5.5 and F5.6 suites re-run 35/35 and 40/40 through the refactored `request()`.
- Level: *browser tested*. No clean-environment run: this is a middleware
  argument, not infra/DDL/seed/env config.

**What was explicitly NOT done**
- `B2.2b` (discovered as `NEW-ABFE02-1`, P3), recorded and not fixed:
  `parse_range` offset handling, a CSV UTF-8 BOM for Excel, and the English 422
  detail.
- No Jalali date picker (dependency decision); native inputs plus a Jalali
  preview.
- Report buckets stay UTC days / Gregorian months as the backend returns them.
- Not touched: AB-FE-05, F4.3, F5.9, F5.10.
- Docs left untouched: `infra/README.md`, `vogue-vintage-vibes/README.md` and
  the spec.

**Decisions taken**
1. The backend CORS change was allowed because the existing contract could not
   meet the "honour the RFC-6266 filename" acceptance criterion cross-origin.
2. The capability guard relies on the backend plus the existing role-gated tabs.
   `/admin/orders` and `/admin/products` are granted to exactly the `orders`
   capability roles, so no third copy of the role matrix was added.
3. The report only displays backend figures; the frontend sums nothing.
4. The stale FEATURES.md rows ۶.۱۲ and ۶.۱۵ (no reports / no Excel) were
   corrected.

→ audit: [2026-09-22-abfe02-admin-export-controls.md](audit/2026-09-22-abfe02-admin-export-controls.md)

**Next backlog pointer** — `AB-FE-05` (admin products server pagination); the
`admin.products.tsx` collision with AB-FE-02 is cleared.

## 2026-09-22 — AB-FE-05 admin products server pagination

**AB-FE-05 — done.** `/admin/products` no longer renders the whole
`useCatalog()` list:
- It reads 20-row pages of `GET /products?include_inactive=true` under its own
  `["admin-products"]` key. The shared `["catalog"]` stays for the storefront.
- Page, category and availability live in the URL. Filters survive paging, and
  any filter change resets the page.
- Server total in the heading, the shared `Pager`, and `keepPreviousData` so a
  page change dims the old rows instead of blanking.
- Skeleton, error + retry, and filtered/unfiltered empty states. An out-of-range
  page moves to the last page (only once real data is known).
- Product save/delete and `VariantEditor` invalidate the new key.

**Router bug fixed on this route** — TanStack Router merges a route's validated
search over the parent's raw search, so keys that `validateSearch` omits leak
through (`?page=abc` reached the API). Rejected keys are now returned as explicit
`undefined`. `/shop` has the same leak (F5.11).

**Verification**
- Frontend: tsc clean; lint 0 errors; build OK.
- Backend (untouched): pytest 72, ruff clean, `api_smoke.py` 196/0.
- Headless Chromium over 25 throwaway fixture products (45 total, 3 pages): 36/36,
  run twice. The fixtures were deleted and the catalogue is back to 20.
- F5.5 / F5.6 / AB-FE-02 suites re-run: 35/35, 40/40, 45/45.
- Level: *browser tested*.
- Earlier runs had timing failures (the script read placeholder rows), fixed by
  waiting for the response and for `aria-busy` to clear. One hollow `|| true`
  assertion in my script was replaced by a real check before the passing runs.

**What was explicitly NOT done**
- No text search: `GET /products` has no `q`.
- Remaining whole-catalogue fetch: `CartProvider` in `__root.tsx` fetches the
  catalogue on every route (1× on `/admin/products`, 1× on `/admin/orders`).
  Recorded as `F5.12` (P2).
- `B5.4b` (P2, backend): `include_inactive` is gated on `is_admin`, so
  order_manager sees 39 of 44 rows and cannot re-activate products.
- `F5.11` (P3): the `/shop` URL param leak.
- Delete still has no confirmation.
- Docs left untouched: `backend/README.md`, `infra/README.md`,
  `vogue-vintage-vibes/README.md` and the spec.

**Decisions taken**
1. A separate `["admin-products"]` query instead of changing `catalogQuery`,
   because six storefront and admin consumers depend on it.
2. Category and availability were chosen as the page's filters because they are
   the server-supported facets that matter to catalogue work.
3. Page size 20, like the other admin lists.
4. The `validateSearch` explicit-`undefined` rule was documented in
   DESIGN_SYSTEM.md for future routes.

→ audit: [2026-09-22-abfe05-admin-products-pagination.md](audit/2026-09-22-abfe05-admin-products-pagination.md)

**Next backlog pointer** — `B3.11` (contact-form spam guard, P1, Batch F; backend +
DB). Batch B is complete apart from F5.9 (P2).

## 2026-09-22 — B3.11 contact-form spam guard

**B3.11 — done (decision D1).** `POST /contact` now goes through
`services/contact_guard.py`:
- Every attempt is written to the new `contact_attempts` table. An IP gets 5
  attempts per sliding 10 minutes; accepted, honeypot and throttled attempts all
  count. A per-IP `pg_advisory_xact_lock` serialises the count-and-insert.
- A filled honeypot field `website` → generic Persian 400, nothing stored.
  Throttled → generic Persian 429 (no `Retry-After`, no counts).
- Rejected attempts are committed before raising, because `get_session` rolls back
  on errors.
- Frontend: the form carries an off-screen, `aria-hidden`, untabbable `website`
  input (present in the SSR HTML), and a 429 shows the server's text.

**Found and fixed in place (R7/R9)** — the shared client-IP resolver (B5.1a audit
middleware) took the first `X-Forwarded-For` entry from any caller. No proxy
exists in this repo (compose publishes :8000 directly), so the throttle and the
audit IPs would both have been spoofable. The new `services/client_ip.py` believes
XFF only when the socket peer is in `TRUSTED_PROXIES` (empty by default) and walks
the chain right to left. `TRUSTED_PROXIES`, `CONTACT_RATE_LIMIT` and
`CONTACT_RATE_WINDOW_SECONDS` are in config, compose and `.env.example`.

**Verification**
- 20 new tests; full pytest 92 passed; ruff clean.
- Mutation checks: lock / commit-before-raise / trusted-proxy check / honeypot
  each turn their tests red (the lock-free burst failed 3 out of 3 runs).
- Clean environment `down -v && up -d --build`: `db-init` exit 0 through all four
  stages, services healthy, `/health` OK, table and indexes on the fresh DB.
- `api_smoke.py` 199/0.
- Live curl: rotating spoofed XFF → `201×5, 429×2`; audit IP not spoofable.
- Browser `/contact` 10/10, 6 consecutive runs.
- F5.6 / AB-FE-02 / AB-FE-05 browser suites green on the rebuilt stack.
- Level: *fully verified*.

**Mistakes in my own tests, found and fixed**
- An IPv6-canonicalisation cleanup leak in one test.
- Shell quoting in the browser helper.
- A digit-script mismatch in one assertion.
- My endpoint docstring advertised the honeypot in the public OpenAPI. It was
  moved to a code comment, and `/openapi.json` was checked to be clean of every
  mechanism keyword.
- A pre-hydration click race in the browser harness. It is now waited on
  deterministically. It is the likely cause of 1 intermittent failure in 8 early
  runs, which could not be reproduced afterwards.

**What was explicitly NOT done**
- No throttle on other public endpoints (D1 covers `/contact` only).
- No cleanup job beyond the per-attempt 1-day pruning.
- The local non-docker uvicorn `--proxy-headers` default (trusts 127.0.0.1) is
  documented, not changed.
- The F5.5 browser suite was not re-run: the wiped DB lacks the ≥26 audit rows it
  needs.
- Docs left untouched: `vogue-vintage-vibes/README.md`, `DESIGN_SYSTEM.md` and the
  spec.

**Decisions taken**
1. A 400 for the honeypot rather than a fake 201, so a person whose browser
   autofills the hidden field sees an error instead of false success.
2. 422 schema errors are not counted: FastAPI rejects them before the handler, and
   they store nothing.
3. Canonical homes were added to RULES.md Rule 7 (client IP, contact guard).
4. Dev note in `infra/README.md`: the host shares one bucket (docker gateway IP),
   with a one-line reset.

→ audit: [2026-09-22-b311-contact-spam-guard.md](audit/2026-09-22-b311-contact-spam-guard.md)

**Next backlog pointer** — `B2.1` (SMS/email notifications, P1). Check the
stop conditions first: real Kavenegar/SMTP credentials are probably not
available.

## 2026-09-22 — B2.1 notification infrastructure

**Task.** `B2.1` from the Master Backlog, under the user's explicit product
adjustment: no real Kavenegar/SMTP credentials exist, so build the in-app
notification system for real, the SMS/email layer ready-but-inactive, and admin
on/off switches that never affect in-app notifications. First turn of the session
was only "check next task" → reported B2.1 and the missing-credentials stop
condition; the user then supplied the adjusted brief.

**What was done**
- `backend/app/services/notifications.py` — the one entry point. In-app
  `notifications` rows are inserted on the business session at the lifecycle
  point (checkout; gateway verify, simulator and staff `payment_status=paid`;
  staff PATCH to `shipped`; `cancel_order_tx`; refund `approved` / `refunded`),
  deduplicated by `UNIQUE (user_id, event_key)`.
- SMS/email: `notification_deliveries` outbox rows only for channels the admin
  switched on, sent by a background task after the commit
  (SQLAlchemy `after_commit`, SAVEPOINT releases ignored, rollback drops the
  queue). Providers `KavenegarSmsProvider` / `SmtpEmailProvider` read env
  config only; both unconfigured → rows are `skipped`, nothing is sent, the order
  flow is untouched. Failures are stored (`failed` + `last_error`); re-dispatch
  is retry-safe.
- Admin switches: `notification_settings` (single row, both off) +
  `GET/PATCH /admin/settings/notifications` behind a new `settings` capability
  (admin/super_admin), audited.
- Inbox API: `GET /notifications` (envelope), `/unread-count`, `PATCH …/read`,
  `POST /read-all`, all owner-scoped in SQL.
- UI: header bell (in `SiteHeader`, which `__root` renders on every route),
  `/account/notifications`, `/admin/settings`; `ui/switch.tsx` RTL thumb bug fixed
  in place (it slid out of the track; the coupons toggle had it too).
- Compose/env examples carry the provider variables with empty defaults.
- Docs: D2 product adjustment + B2.1 DONE + pointer/counts in the Master Backlog,
  task files, READMEs, FEATURES, roadmap, DESIGN_SYSTEM, RULES (canonical table),
  AGENTS.md (R7 line).

**Verification**
- 45 new tests; mutation checks (dedup, switch, re-send, missing hook) turn them red.
- pytest 137 passed with `DATABASE_URL` exported (92 → 137); ruff clean;
  `api_smoke.py` 224/0 — on the dev stack and again after `down -v`.
- Clean environment: `db-init` exit 0 through all four stages, `/health` OK,
  tables/constraints/indexes/settings row on the fresh DB, 0 notifications after
  seeding, provider env vars empty in the container.
- Frontend tsc / lint (0 errors) / build OK.
- Browser: B2.1 suite 58/58 (three dev-stack runs + clean stack); role/route
  regression sweep 52/54 on the clean stack, both failures pre-existing (below).
- Level: *fully verified* for the in-app system, switches and provider layer up to
  the provider boundary. **No real SMS/email was sent** — B2.1a.

**Mistakes in my own work, found and fixed**
- I first also put a bell in the admin shell header; `SiteHeader` already
  renders on admin routes, so admins saw two bells. The browser suite caught it;
  removed.
- Browser-harness bugs: fixed sleeps against 5–13 s dev-mode page loads made a
  regression sweep look like app failures (I first misread it as dev-server
  degradation); badge digits in nav text broke a label comparison; mocked 500s
  were counted as real 5xx; twice `pkill -f`/`pgrep -f` matched my own shell and
  killed the run, and one patch to the harness silently failed its own assertion
  so the old script ran. All fixed, then re-run.

**Discovered, recorded, not fixed** — B2.1a (real provider activation, P3),
B5.1d (`record_audit` rollback discards the audited mutation, P2), B6.13 (the
documented `pytest -q` skips all 60 live-DB tests, P2), F5.13 (guest hydration
mismatch on a protected-route redirect, P3), **F5.14** (admin coupon create /
edit / toggle all 422 — `text/plain` body; P1), F5.15 (a failed `/auth/me`
signs the user out, P2). F5.13–F5.15 were each confirmed pre-existing (A/B with
the bell removed, or curl).

**What was explicitly NOT done**
- No real SMS/email delivery; no retry sweeper (B2.5); no password-reset or
  preorder hooks (no such flows — F2.3, B4.13); no ops alerts, "delivered" or
  "refund rejected" notifications (outside D2); no notification deletion/archive
  or retention; no push — the bell polls every 60 s.
- The spec's Part C #8 still says "Pending" (user's document, untouched);
  `vogue-vintage-vibes/README.md` untouched (nothing it lists changed).

**Decisions taken**
1. Outbox + after-commit dispatch instead of sending inside the transaction or
   adding a job system (B2.5 owns jobs).
2. A notification insert error fails the request (atomicity) rather than being
   swallowed; only external sends are isolated.
3. `GET /notifications` always returns the pagination envelope (new endpoint, no
   legacy bare-list callers).
4. Switches default off and may be on while unconfigured — the UI says plainly
   that nothing is sent until the server has credentials.
5. The Switch RTL bug was fixed in the shared primitive (R7), not worked around.
6. Pointer set to **F5.14** before F2.3: both P1, but F5.14 is a broken shipped
   feature with a two-call-site fix; F2.3 also has an SMTP stop condition.

→ audit: [2026-09-22-b21-notification-infrastructure.md](audit/2026-09-22-b21-notification-infrastructure.md)

**Next backlog pointer** — `F5.14` (admin coupon 422 regression, P1), then
`F2.3` (forgot password, P1; reset email through `services/notifications.py`,
SMTP unconfigured → check the stop conditions).

## 2026-09-22 — F5.14 admin coupon 422 (first of the back-to-back run)

**Context.** The user asked to run the remaining pointer + follow-up tasks back to
back: F5.14 → F2.3 → F5.15 → B6.13 → B5.1d → B2.1a → F5.13, one audit/commit each.

**What was done** — `api.adminCreateCoupon` / `api.adminUpdateCoupon` sent a raw
`body: JSON.stringify(…)`, so the browser used `text/plain` and FastAPI answered 422
for every coupon create, edit and toggle. Both now pass `json:`. `request()`, the
backend and the payload are unchanged.

**Verification** — browser 14/14 on `/admin/coupons` (create, toggle off/on, edit,
delete, duplicate → Persian 409 error, empty discount → client error; every write
`application/json`); prettier/tsc/lint/build clean. Level: *browser tested*.

**Discovered, recorded, not fixed** — F5.16 (P2): the edit dialog cannot clear
expiry / total cap / discount kind (sends `null`, PATCH ignores it).

**Not done** — F5.16, F5.9.

→ audit: [2026-09-22-f514-coupon-json-body.md](audit/2026-09-22-f514-coupon-json-body.md)

**Next backlog pointer** — `F2.3`.

## 2026-09-23 — F2.3 forgot password (back-to-back run, task 2)

**What was done** — `password_reset_tokens` (SHA-256 only), `services/password_reset.py`,
`POST /auth/password/forgot` (identical 202 for unknown / known / throttled
addresses) and `POST /auth/password/reset` (400 for a bad link); links last 30 min,
work once, are superseded by a newer request, ≤3 per account per hour. The email goes
through a new `notifications.queue_private_email()` (email switch + SMTP, after COMMIT,
never persisted — the outbox row would store the secret). UI: `/forgot-password`,
`/reset-password`, the link on `/auth`, a channel note on `/admin/settings`.

**Decision taken (stop-condition check)** — SMTP is unconfigured, so no real reset
email can be delivered. No dev shortcut exposes the link (it would be an
account-takeover path); tests use a stub provider and the browser test inserts a
hash-only fixture link. Local testing: point `SMTP_*` at a mail catcher.

**Verification** — 14 new tests (mutation-checked: one-time use, throttle,
enumeration); pytest 151; smoke 229/0; browser 20/20 incl. a full UI reset and a
login with the new password; clean environment (`db-init` four stages, table +
indexes, env vars). Level: *fully verified* except real email delivery.

**Harness fixes** — wait for React's fiber on `<form>` before clicking (pre-hydration
native submit); issue the fixture link after the test's own forgot request (the app
correctly superseded it).

**Discovered** — B6.14 (P2): a reset does not end existing sessions (stateless JWTs).

**Not done** — B6.14, real delivery (B2.1a), per-IP limit on forgot, confirmation
email after a change.

→ audit: [2026-09-23-f23-forgot-password.md](audit/2026-09-23-f23-forgot-password.md)

**Next backlog pointer** — `F5.15`.

## 2026-09-23 — F5.15 a failed `/auth/me` no longer signs the user out (task 3)

**What was done** — `AuthProvider.refresh()` clears the token only on 401/403/404;
a network error, an interrupted request or a 5xx keeps the token and the user and
retries after 1 s / 3 s / 10 s (sign-in/up/out cancel a pending retry).

**Verification** — browser 16/16 (500 → token kept, recovers without reload;
network failure → kept, recovers; garbage token → cleared; deleted account →
cleared; UI sign-in/out). Negative control: the same suite against the old file
fails the 4 transient-error checks. tsc/lint/build clean. Level: *browser tested*.

**My mistake, found and fixed** — the first suite also passed against the old code:
`/auth/me` fires 2–3 s after load in dev, so a fixed wait checked too early. The
suite now waits until the mocked endpoint was actually hit. I re-checked that the
earlier A/B conclusions (F5.13, F5.15 pre-existing) still hold: Vite logged the
reload of each swapped file and those runs compared real observed outcomes.

**Not done** — no "connection lost" banner; `_authenticated`'s guard still redirects
to `/auth` on a transient failure (it recovers through the retry).

→ audit: [2026-09-23-f515-auth-refresh-keeps-session.md](audit/2026-09-23-f515-auth-refresh-keeps-session.md)

**Next backlog pointer** — `B6.13`.

## 2026-09-23 — B6.13 `pytest -q` runs the live-DB tests again (task 4)

**What was done** — new `backend/tests/conftest.py` with the one test-session default
(compose `DATABASE_URL`, `JWT_SECRET`, both `setdefault`); the four dummy `u:p@…/db`
URLs removed from the unit-test modules. `backend/README.md` corrected.

**Verification** — documented command, no env vars: 79 passed / 72 skipped (before,
measured on the same tree) → 151 passed / 0 skipped; database unreachable → clean
skips; ruff clean. Level: *locally tested*.

**Not done** — the now-redundant compose-URL `setdefault` lines in the live-DB
modules were left (no-ops, minimal diff).

→ audit: [2026-09-23-b613-pytest-runs-db-tests.md](audit/2026-09-23-b613-pytest-runs-db-tests.md)

**Next backlog pointer** — `B5.1d`.

## 2026-09-23 — B5.1d audited mutations are all-or-nothing (task 5)

**What was done** — `record_audit` no longer rolls back and carries on (which
silently discarded the audited change while the router answered 200); it logs and
re-raises, so the request fails with 500 and the whole transaction rolls back. All
18 call sites record before committing (checked), so each is now atomic.

**Decision taken** — all-or-nothing over a SAVEPOINT, following B5.1's own rule that
an admin action must not exist without its trail. Reversible if availability is
preferred.

**Verification** — 6 tests with a real trigger-forced audit failure (status change;
staff cancel incl. stock restore + notification; customer cancel; refund settlement
incl. payment row; coupon edit; normal-path control). Negative control: the old code
fails 5. pytest 157, ruff clean, smoke 229/0. Level: *integration tested*.

→ audit: [2026-09-23-b51d-audit-atomicity.md](audit/2026-09-23-b51d-audit-atomicity.md)

**Next backlog pointer** — `B2.1a` (needs real credentials), then `F5.13`.
