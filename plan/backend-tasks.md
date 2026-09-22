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

- [x] **B6.1 Order state machine (spec BE-05)** — `app/services/order_lifecycle.py`:
  transition map enforced in `PATCH /orders/{id}` (409 on illegal moves) and both
  cancel paths; cancellation restores stock (variants first, then the product
  aggregate) in the same transaction; cancelled/delivered are terminal. Live
  smoke asserts the full flow incl. stock +1 on cancel.
  → audit: [2026-09-21-b61-state-machine-f45-coupons-manager.md](audit/2026-09-21-b61-state-machine-f45-coupons-manager.md)

- [ ] **B2.1 SMS/email notifications** — Kavenegar/National SMS or SMTP on order placed/paid/shipped/cancelled/refund
- [x] **B2.2 Reports & exports** — daily/monthly sales, best-sellers, Excel (openpyxl/pandas) + CSV product import/export
  Done (2026-09-22): `/admin/export/orders.{csv,xlsx}`, `/admin/export/products.{csv,xlsx}`
  (StaffOrders guard, RFC-4180 CSV, RFC-6266 filenames) + `/admin/export/report`
  (daily/monthly revenue excluding cancelled, top-10 best-sellers). openpyxl added;
  backend image rebuilt. CSV product *import* split out — see new checkbox below.
  → audit: [2026-09-22-b22-reports-exports.md](audit/2026-09-22-b22-reports-exports.md)
- [ ] **B2.2a CSV product import** — bulk upsert from CSV; needs an overwrite/
  skip policy decision (idempotency key: product id vs name+category) before building
- [ ] **B2.3 PDF invoices** — reportlab/weasyprint, Persian digits, per-order invoice endpoint
- [x] **B2.4 Recommendation engine** — related products from co-purchase patterns
  Done (2026-09-22): `co_purchases` pair table (canonical pairs, DDL in startup)
  refreshed in the checkout transaction for multi-item carts + at startup;
  `/products/{id}/recommendations` blends votes ×3 with the category/popularity
  heuristic (identical payload; `/related` untouched). Learned pairs verified live.
  → audit: [2026-09-22-b24-co-purchase-recommendations.md](audit/2026-09-22-b24-co-purchase-recommendations.md)
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
- [x] **B3.4 Clean stale Supabase wording in code** — `app/db.py`, `app/models.py`,
  `routers/auth.py`, `routers/storage.py`, `seed_products.py`: every remaining
  Supabase reference now describes the FastAPI + own-JWT + MinIO reality
  (`grep -ri supabase backend/app backend/tests` → nothing).
  → audit: [2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md](audit/2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md)
- [x] **B3.6 Stack actually runs in Docker** — MinIO images moved to `quay.io`
  (Docker Hub publishing stopped Oct 2025), `minio-init` reuses the bundled `mc`,
  and the 7 runtime bugs it exposed are fixed (password hashing was fully broken;
  coupon seeding order; `auth.users` in the coupon DDL; `/search` param type;
  `/admin/stats` FILTER placement; MinIO presign int-vs-timedelta + host/region;
  payment callback always 404ing).
  → audit: [2026-09-19-docker-stack-up-and-runtime-fixes.md](audit/2026-09-19-docker-stack-up-and-runtime-fixes.md)
- [x] **B3.7 Persist the payment authority** — a repeat Zarinpal callback returned
  400 instead of `already_paid`, because `reference` was overwritten with the
  `SND-…` code during verification. `payments.authority` (+ index) is now created
  on startup, `verify_and_finalize` looks the session up by authority (with a
  `reference = :authority` fallback for pre-column rows) and reports
  `already_paid` for a settled session, and the callback reads the order from the
  verify result so the repeat still redirects correctly.
  → audit: same as B3.4
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
- [x] **B3.9 `POST /contact` + admin inbox endpoints** — `contact_messages` table
  (idempotent DDL in `app/db.py`), public `POST /contact` (guest-friendly,
  `user_id` NULL, name ≥ 2 / contact ≥ 5 / message ≥ 5), and
  `GET /admin/contact-messages?status=` + `DELETE /admin/contact-messages/{id}`.
  The storefront form is wired (F2.1); the admin inbox screen is **F2.1b**.
  → audit: [2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md](audit/2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md)
- [x] **B3.10 Address book: single default + `PATCH`** — at most one `is_default`
  per customer (first address becomes it, an explicit flag moves it, deleting the
  default promotes the newest survivor) and `PATCH /addresses/{id}` edits fields
  and/or moves the default. `CheckoutAddress` also gained the optional `province`
  the spec's shipping box asks for, and it is stored in `orders.shipping_address`.
  → audit: same as B3.9
- [x] **B3.12 Shipment tracking code on orders** — additive `orders.tracking_code`
  column (idempotent `TRACKING_DDL` in `app/db.py`), accepted by
  `PATCH /orders/{id}` (admin-only; empty string clears it) and returned in every
  order payload. The payment-session `tracking_code` is a different, pre-existing
  value and is untouched. Smoke asserts save / customer-visibility / clear / 403.
  → audit: [2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md](audit/2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md)
- [x] **B3.13 Mark a contact message answered** — `PATCH
  /admin/contact-messages/{id}` (`status`: `new` | `answered`, validated with a
  `Literal` schema) so the F2.1b inbox can work through its backlog; unknown
  statuses 422. Smoke asserts mark + `?status=answered` filter + 422.
  → audit: same as B3.12
- [ ] **B3.11 Spam guard for the public contact endpoint** — `POST /contact` is an
  unauthenticated write with no rate limit, honeypot or captcha. Decide the
  approach (per-IP throttle vs honeypot field) before opening a public deploy.

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
- [x] **B4.12 Multi-value catalog filters** — `GET /products` now takes `size`
  and `color` as repeatable and/or comma-separated lists
  (`app/services/catalog_filters.py::split_multi`), OR within a facet and AND
  across facets, resolved **per combination** so a variant-deactivated pair is not
  advertised. The shop sidebar is multi-select (F3.3c).
  → audit: [2026-09-21-backend-b411-b412-availability-multifacet.md](audit/2026-09-21-backend-b411-b412-availability-multifacet.md)
- [x] **B4.11 Enforce `availability` in stock-check and checkout** — new
  `app/services/availability.py` gate, applied before stock in both
  `POST /stock/check` and checkout; `preorder` is blocked too (user decision).
  `StockIssue.reason` is now a documented closed set including `not_available` and
  `size_invalid`.
  → audit: same as B4.12
- [ ] **B4.13 Preorder fulfilment flag** — `preorder` products can never be
  ordered while `orders` has no preorder marker. Add the flag + relax
  `availability_issue()` if the store wants to take preorders (depends on the
  fulfilment/notification story, B2.1).
- [ ] **B4.8 Product model dimension** — variants cover size × color only; add a
  model/name dimension if the catalog needs it
- [ ] **B4.9 Stock reservation with TTL** — hold stock during checkout instead of
  decrementing only at order creation

## Milestone B5 — Spec-only backend work (from `design/SANDE_FULL_DEV_SPEC.md`)

Gaps the dev spec names that have no backend task yet. Only the parts that are not
already covered by B2.1/B2.2/B2.5 — read the spec first (Rule 0), but the repo's
architecture (FastAPI, own JWT, no Supabase) is binding (Rule 0.2).

- [x] **B5.1 Admin audit log** — `audit_logs` table (idempotent `AUDIT_DDL`) +
  `app/services/audit.py::record_audit` wired into the privileged mutations:
  order status/payment/tracking changes, cancel, refund resolution (incl. bank
  code), product/variant/coupon create-update-delete with old→new values, review
  moderation. Admin-only `GET /admin/audit-logs` with action/entity/admin filters.
  Spec BE-04. IP capture and DB-level tamper-resistance split off (below).
  → audit: [2026-09-21-backend-b51-audit-log.md](audit/2026-09-21-backend-b51-audit-log.md)
- [x] **B5.1a Audit IP capture** — `client_ip_ctx` contextvar set by the
  `capture_client_ip` middleware (XFF-aware, socket fallback); `record_audit`
  falls back to it, so all audit sites record the caller IP with no signature
  churn. Verified live + smoke assertion.
  → audit: [2026-09-21-b51a-audit-ip-f41-status-badges.md](audit/2026-09-21-b51a-audit-ip-f41-status-badges.md)
- [ ] **B5.1b Audit tamper-resistance at the DB level** — REVOKE UPDATE/DELETE on
  `audit_logs` for the app role (append-only) in `infra/initdb` or startup DDL.
- [x] **B5.2 KPI aggregation endpoint** — `GET /admin/kpis?range=today|7d|30d|all`
  returning gross/net revenue, paid order count, AOV, pending refunds and low-stock
  count, plus daily revenue series + status breakdown and deltas vs the preceding
  window; replaces the client-side aggregation the dashboard did. Spec BE-09;
  consumed by F2.6.
  → audit: [2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md](audit/2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md)
- [x] **B5.3 Refund bank-tracking fields** — `refund_requests` gained
  `bank_tracking_code`, `resolved_by` (FK → users) and `resolved_at`
  (idempotent `REFUND_DDL` in `app/db.py`). Vocabulary reconciled: new rows are
  inserted as `pending` explicitly and a startup UPDATE normalizes legacy
  `requested` rows; settled states are untouched. `PATCH /refunds/{id}` now
  requires the bank code when settling (`refunded`), records the resolver and
  timestamp on every resolution, and `GET /admin/refunds` carries the claimant's
  name/email. F2.4's dialog takes the required Paya/Satna code; [BE-03]/[FE-06]
  are now satisfied end-to-end. Smoke: 130 checks, 0 failed.
  → audit: [2026-09-21-backend-b53-refund-bank-tracking.md](audit/2026-09-21-backend-b53-refund-bank-tracking.md)
- [x] **B5.4 Granular staff roles** — `super_admin` / `order_manager` / `support`
  alongside the current binary `admin`/`customer`, enforced per route. Spec BE-04
  (security rule: roles stay in their own table, never on the user row).
  `ROLE_DDL` extends the enum; `require_staff(capability)` guards every staff
  route via `ROLE_CAPABILITIES`; `PUT /admin/users/{id}/roles` manages role sets
  (audited as `update_user_roles`); demo staff accounts seeded. Smoke: 156
  checks, 0 failed — capability matrix asserted end-to-end.
  → audit: [2026-09-21-backend-b54-granular-staff-roles.md](audit/2026-09-21-backend-b54-granular-staff-roles.md)

## Ideas (not scheduled)

- [ ] Redis cache for product catalog
- [ ] Rate limiting on checkout/payment endpoints
- [ ] Locale switch (i18n) for API error messages
