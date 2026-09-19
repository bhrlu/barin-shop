# Backend Task List (backend/)

Legend: `[ ]` todo · `[x]` done (audit file required) · audit links in `plan/audit/`

## Milestone B1 — Core service (Part 7, lean MVP)

- [x] **B1.1 Scaffold FastAPI project** — pyproject, app package, config, env example
  → audit: [2026-09-19-backend-scaffold.md](audit/2026-09-19-backend-scaffold.md)
- [x] **B1.2 DB layer** — async SQLAlchemy engine, models mirroring Supabase schema, coupon-table DDL
  → audit: [2026-09-19-backend-scaffold.md](audit/2026-09-19-backend-scaffold.md)
- [x] **B1.3 Supabase JWT auth + roles** — HS256 verify, aud=authenticated, admin/customer from user_roles
  → audit: same file as B1.1
- [x] **B1.4 Real coupon system** — coupons + coupon_redemptions tables, validate/create/list/update endpoints, usage caps, seed SANDE10 + WELCOME500
  → audit: same file as B1.1
- [x] **B1.5 Transactional stock decrement** — FOR UPDATE locks, guarded decrement, server-side prices
  → audit: same file as B1.1
- [x] **B1.6 Zarinpal payment gateway** — request/verify, callback with redirect, simulation mode, manual verify for polling clients
  → audit: same file as B1.1
- [x] **B1.7 Product search** — ILIKE search ranked name > category > description, pagination
  → audit: same file as B1.1
- [x] **B1.8 Tests + lint clean** — 19 unit tests, ruff clean, OpenAPI smoke test
  → audit: same file as B1.1
- [x] **B1.9 Backend became the sole service (no Supabase)** — own JWT auth
  (`security.py`/`auth.py`/`seed_auth.py`), real `public.users`, new routers
  (auth, products, orders, addresses, favorites, admin, storage), MinIO storage;
  40 operations across 34 paths. **Done unlogged** (see Session 3) — no tests for
  the new routers yet.
  → audit: [2026-09-19-sole-backend-no-supabase.md](audit/2026-09-19-sole-backend-no-supabase.md)

## Milestone B2 — Remaining Part-7 features (not started)

- [ ] **B2.1 SMS/email notifications** — Kavenegar/National SMS or SMTP on order placed/paid/shipped/cancelled/refund
- [ ] **B2.2 Reports & exports** — daily/monthly sales, best-sellers, Excel (openpyxl/pandas) + CSV product import/export
- [ ] **B2.3 PDF invoices** — reportlab/weasyprint, Persian digits, per-order invoice endpoint
- [ ] **B2.4 Recommendation engine** — related products from co-purchase patterns
- [ ] **B2.5 Webhooks + background jobs** — order events, abandoned-payment reminders, APScheduler
- [ ] **B2.6 Coupon admin UI support** — nothing to build in Python; expose whatever the admin panel needs (done as part of B1.4 API)
  → superseded by B1.9: `/admin/*` endpoints + `/coupons` CRUD now exist; the panel
  still needs wiring (frontend F1.2 / F2.4)

## Milestone B3 — Pay down debt from the sole-service rewrite

- [x] **B3.1 Fix `DATABASE_URL` examples** — `postgresql://` → `postgresql+asyncpg://`
  in `backend/.env.example`, `infra/.env.example`, `infra/docker-compose.yml`
  (startup failed with `ModuleNotFoundError: psycopg2`)
  → audit: [2026-09-19-sole-backend-no-supabase.md](audit/2026-09-19-sole-backend-no-supabase.md)
- [x] **B3.2 Refresh `backend/README.md`** — Supabase auth story removed; the sole-backend
  architecture, own-JWT auth, all routers, the new catalog endpoints, the stock model,
  catalog DDL and the test commands are documented.
  → audit: [2026-09-20-catalog-backend-and-address-fix.md](audit/2026-09-20-catalog-backend-and-address-fix.md)
- [x] **B3.3 Refresh `infra/README.md`** — dropped `01-auth-shim.sql` and "Supabase stays
  hosted"; documents the sole-backend stack, MinIO-on-quay, presign host, idempotent
  catalog DDL and the seed chain.
  → audit: same as B3.2
- [ ] **B3.4 Clean stale Supabase wording in code** — `app/db.py` docstring/comments,
  `app/models.py` if applicable
- [x] **B3.6 Stack actually runs in Docker** — MinIO images moved to `quay.io`
  (Docker Hub publishing stopped Oct 2025), `minio-init` reuses the bundled `mc`,
  and the 7 runtime bugs it exposed are fixed (password hashing was fully broken;
  coupon seeding order; `auth.users` in the coupon DDL; `/search` param type;
  `/admin/stats` FILTER placement; MinIO presign int-vs-timedelta + host/region;
  payment callback always 404ing).
  → audit: [2026-09-19-docker-stack-up-and-runtime-fixes.md](audit/2026-09-19-docker-stack-up-and-runtime-fixes.md)
- [ ] **B3.7 Persist the payment authority** — a repeat Zarinpal callback returns
  400 instead of `already_paid`, because `reference` is overwritten with the
  `SND-…` code during verification. Needs an authority column (schema change
  decision) or an equivalent lookup path.
- [x] **B3.8 Fix `HTTPException` with two `detail`s** — coupon/stock failures raised
  `HTTPException(code, message, detail={...})`, so every checkout error returned a
  **500** instead of a clean 4xx. `routers/checkout.py` and `routers/payments.py`
  now pass one `detail` object (`{message, code, issues}`). Found during the first
  end-to-end Docker run.
  → audit: [2026-09-19-e2e-flow-docker.md](audit/2026-09-19-e2e-flow-docker.md)
- [x] **B3.5 Tests for the new routers** — `test_addresses.py` (the created_at
  regression), `test_variants.py` (variant-stock resolver), and `tests/api_smoke.py`
  (live end-to-end: logs in as customer + admin and exercises every route, reporting
  5xx). Unit suite: 25 passed, ruff clean. A pytest DB fixture for router-level unit
  tests is still open (smoke needs a running server).
  → audit: same as B3.2

## Milestone B4 — Catalog & Products backend (complete)

Closes the backend half of `plan/feature-roadmap.md` §1. Idempotent DDL lives in
`app/db.py` (`CATALOG_DDL`).

- [x] **B4.1 Product merchandising** — `tags`, `badge`, `availability`
  (`in_stock`/`coming_soon`/`preorder`), `available_at`, `low_stock_threshold`; reads
  expose `avg_rating` + `review_count`
  → audit: [2026-09-20-catalog-backend-and-address-fix.md](audit/2026-09-20-catalog-backend-and-address-fix.md)
- [x] **B4.2 Catalog filters + sort** — `GET /products` gained `tag`, `badge`,
  `availability`, `on_sale`, `size`, `color`, `min_price`, `max_price`, `sort`
  (`new|price_asc|price_desc|popular|rating`)
  → audit: same as B4.1
- [x] **B4.3 Variants (size × color) with per-combination stock** — CRUD +
  authoritative stock wired into `POST /stock/check` and checkout
  → audit: same as B4.1
- [x] **B4.4 Reviews & ratings + seller replies** — list/create/delete, admin
  moderation, rating summary + distribution
  → audit: same as B4.1
- [x] **B4.5 Search autocomplete + history** — `GET /search/suggest`,
  `GET/DELETE /search/history`, recorded on `GET /search`
  → audit: same as B4.1
- [x] **B4.6 Related / recommended / compare / recently viewed**
  → audit: same as B4.1
- [x] **B4.7 Low-stock inventory** — `GET /admin/inventory`, `/admin/inventory/low-stock`
  → audit: same as B4.1
- [x] **B4.10 Search matches product tags** — `GET /search` matched name,
  description, material and category but not `tags`, so the tag suggestions from
  `/search/suggest` led nowhere; and no seeded product had tags at all. The
  matcher now includes `tags` (ranked name > category > tag > description),
  `app/seed_products.py` tags all 20 starter products and backfills tags only on
  rows that have none, and `tests/api_smoke.py` asserts tag hits + tag
  suggestions.
  → audit: [2026-09-20-backend-search-tags.md](audit/2026-09-20-backend-search-tags.md)
- [ ] **B4.12 Multi-value catalog filters** — `GET /products` accepts a single
  `size` and a single `color`, so the shop sidebar is single-select (F3.3). Accept
  repeated or comma-separated values (and consider dropping the AND semantics
  trap: a size+colour pair should ideally mean "this combination exists").
- [ ] **B4.11 Enforce `availability` in stock-check and checkout** — the
  storefront (F3.2) disables add-to-cart for `coming_soon`/`preorder`, but
  `app/services/checkout.py` validates only stock/activity/size, so a direct API
  call can still order an unreleased product. Add the guard to `stock/check` and
  checkout (and decide whether `preorder` should be orderable with a different
  fulfilment note).
- [ ] **B4.8 Product model dimension** — variants cover size × color only; add a
  model/name dimension if the catalog needs it
- [ ] **B4.9 Stock reservation with TTL** — hold stock during checkout instead of
  decrementing only at order creation

## Ideas (not scheduled)

- [ ] Redis cache for product catalog
- [ ] Rate limiting on checkout/payment endpoints
- [ ] Locale switch (i18n) for API error messages
