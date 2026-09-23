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

- [x] **B2.1 SMS/email notifications** — Kavenegar/National SMS or SMTP on order placed/paid/shipped/cancelled/refund
  Done (2026-09-22) as **notification infrastructure** (user decision: no real
  credentials exist). `services/notifications.py` is the one entry point: an
  in-app `notifications` row per user per event, written on the business session
  at the lifecycle point (order created / paid / shipped / cancelled, refund
  approved / settled), deduplicated by `UNIQUE (user_id, event_key)`. Admin SMS /
  email switches (`notification_settings`, `GET/PATCH /admin/settings/notifications`,
  new `settings` capability = admin/super_admin) feed a `notification_deliveries`
  outbox that is sent after the commit and never fails the business transaction.
  `KavenegarSmsProvider` / `SmtpEmailProvider` read env credentials only; both are
  unconfigured → nothing is sent. Inbox API `GET /notifications`,
  `/notifications/unread-count`, `PATCH /notifications/{id}/read`,
  `POST /notifications/read-all`; header bell + `/account/notifications` +
  `/admin/settings` UI. 45 new tests. Real delivery **not** verified (no credentials).
  → audit: [2026-09-22-b21-notification-infrastructure.md](audit/2026-09-22-b21-notification-infrastructure.md)
- [ ] **B2.1a Activate the real SMS/email providers** (`NEW-B21-1`, discovered
  during B2.1) — needs real Kavenegar and SMTP credentials (stop and ask if they are
  absent). Set them in `infra/.env`, confirm `*_configured` on
  `/admin/settings`, send one real SMS and one real email end to end, check the
  Kavenegar sender line / template rules and the SMTP TLS mode, and record the
  result. The adapters were only tested against stub transports.
  **Stopped 2026-09-23** (back-to-back run): no credentials in `infra/.env` or the
  backend container — nothing changed; resume when the user supplies them.
- [x] **B2.2 Reports & exports** — daily/monthly sales, best-sellers, Excel (openpyxl/pandas) + CSV product import/export
  Done (2026-09-22): `/admin/export/orders.{csv,xlsx}`, `/admin/export/products.{csv,xlsx}`
  (StaffOrders guard, RFC-4180 CSV, RFC-6266 filenames) + `/admin/export/report`
  (daily/monthly revenue excluding cancelled, top-10 best-sellers). openpyxl added;
  backend image rebuilt. CSV product *import* split out — see new checkbox below.
  → audit: [2026-09-22-b22-reports-exports.md](audit/2026-09-22-b22-reports-exports.md)
- [ ] **B2.2a CSV product import** — bulk upsert from CSV; needs an overwrite/
  skip policy decision (idempotency key: product id vs name+category) before building
- [ ] **B2.2b Export date/encoding correctness** (`NEW-ABFE02-1`, discovered during
  AB-FE-02) — (1) `services/exports.py::parse_range` uses `.replace(tzinfo=UTC)`,
  so `from=2026-09-22T00:00:00+03:30` is read as UTC midnight: honour the offset
  (`astimezone(UTC)`, naive input stays UTC). (2) The CSV exports have no UTF-8
  BOM, so Excel may garble Persian text when the file is double-clicked.
  (3) A bad date returns an English 422 detail. The AB-FE-02 UI already sends
  naive UTC bounds and validates dates, so it is unaffected. Add pytest
  coverage for the offset case.
- [ ] **B2.3 PDF invoices** — reportlab/weasyprint, Persian digits, per-order invoice endpoint
- [x] **B2.4 Recommendation engine** — related products from co-purchase patterns
  Done (2026-09-22): `co_purchases` pair table (canonical pairs, DDL in startup)
  refreshed in the checkout transaction for multi-item carts + at startup;
  `/products/{id}/recommendations` blends votes ×3 with the category/popularity
  heuristic (identical payload; `/related` untouched). Learned pairs verified live.
  → audit: [2026-09-22-b24-co-purchase-recommendations.md](audit/2026-09-22-b24-co-purchase-recommendations.md)
- [ ] **B2.5 Webhooks + background jobs** — order events, abandoned-payment reminders, APScheduler
  (B2.1 hand-off: add the sweeper that re-dispatches `notification_deliveries` left
  `pending` by a crash and retries `failed` rows with a cap — call
  `services/notifications.dispatch_deliveries()`, which is already retry-safe.)
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
- [x] **B3.11 Spam guard for the public contact endpoint** — `POST /contact` was an
  unauthenticated write with no rate limit, honeypot or captcha. Done per decision
  D1:
  - PostgreSQL per-IP throttle of 5 attempts per 10 minutes (`contact_attempts`,
    serialised by a per-IP advisory lock). Accepted, honeypot and throttled
    attempts all count, and guests and signed-in users share the limit.
  - Honeypot field `website`: 400, not stored. A throttled attempt gets a generic
    Persian 429.
  - The shared client-IP resolver now believes `X-Forwarded-For` only from
    `TRUSTED_PROXIES` (none by default), so the limit and the audit IP can't be
    spoofed.
  - Fully verified, including a clean-environment run.
  → audit: [2026-09-22-b311-contact-spam-guard.md](audit/2026-09-22-b311-contact-spam-guard.md)

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
  fulfilment/notification story, B2.1). B2.1 is DONE: add the preorder
  notification type to `TYPES` in `services/notifications.py` and fire it from
  the preorder lifecycle point with an `order:<id>:…` event key.
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
  `capture_client_ip` middleware (socket peer; `X-Forwarded-For` only from a
  configured trusted proxy since B3.11 — it used to trust any caller's XFF); `record_audit`
  falls back to it, so all audit sites record the caller IP with no signature
  churn. Verified live + smoke assertion.
  → audit: [2026-09-21-b51a-audit-ip-f41-status-badges.md](audit/2026-09-21-b51a-audit-ip-f41-status-badges.md)
- [x] **B5.1b Audit tamper-resistance at the DB level** — REVOKE UPDATE/DELETE on
  `audit_logs` for the app role (append-only) in `infra/initdb` or startup DDL.
  Done (2026-09-23): triggers make `audit_logs` append-only (UPDATE/DELETE/TRUNCATE refused; only the FK `admin_id → NULL` cascade allowed) — REVOKE cannot, the app role owns the table and is a superuser. New guard shapes keep the boot lock-free. 6 tests + negative control; clean env.
  → audit: [2026-09-23-b51b-audit-log-append-only.md](audit/2026-09-23-b51b-audit-log-append-only.md)
- [x] **B5.1d `record_audit` rolls back the mutation it is auditing** (`NEW-B21-2`,
  discovered during B2.1) — on an insert failure `services/audit.py::record_audit`
  calls `session.rollback()` and swallows the error, which also discards the
  order/refund/role change made earlier on the same session; the router then
  commits nothing and still answers 200 with the new values. Use a SAVEPOINT
  (`begin_nested()`) around the audit insert, or let it fail the request —
  decide which, then add a pytest that forces the audit insert to fail.
  Done (2026-09-23): decided all-or-nothing — the failure is logged and re-raised,
  the request answers 500 and nothing is persisted. 6 tests with a real
  trigger-forced failure; the old code fails 5 of them.
  → audit: [2026-09-23-b51d-audit-atomicity.md](audit/2026-09-23-b51d-audit-atomicity.md)
- [ ] **B5.1e Run the backend as a least-privilege database role** (`NEW-B51B-1`,
  discovered during B5.1b) — the app connects as the schema owner and a superuser, so
  it can drop tables or disable the audit triggers. Split a migrator role (DDL, seeds)
  from a DML-only app role; clean-env proof.
- [ ] **B5.1c `GET /admin/audit-logs` 500s on a malformed `admin_id`**
  (`NEW-F55-1`, discovered during F5.5) — `?admin_id=foo` reaches
  `CAST(:admin_id AS uuid)` and Postgres raises, so the admin caller gets a 500
  instead of a 422. Type the query parameter as `UUID` in `routers/admin.py`.
  Admin-only; the F5.5 viewer only sends real UUIDs.
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
- [x] **B5.4a Role-change lockout guard** (`NEW-F56-1`, discovered during F5.6) —
  `PUT /admin/users/{id}/roles` lets a caller demote themselves and remove the
  last `super_admin`; if nobody keeps the `users` capability, roles can only be
  fixed in the DB. Reject self-demotion and removal of the last holder of the
  `users` capability with 409, with a test. The F5.6 UI already disables the
  caller's own row, but that is UX only.
  Done (2026-09-23): 409 when a role change would take role management from the caller or leave nobody holding it; `role_lockout_reason` in `services/roles.py`, serialized by an advisory lock. 9 tests (negative control: self-demotion fails on the old code).
  → audit: [2026-09-23-b54a-role-lockout-guard.md](audit/2026-09-23-b54a-role-lockout-guard.md)
- [x] **B5.4b `include_inactive` follows `is_admin`, not the `catalog` capability**
  (`NEW-ABFE05-1`, discovered during AB-FE-05) — `GET /products` shows inactive
  products only to admin/super_admin, so an `order_manager` (who may edit the
  catalogue) never sees inactive products in `/admin/products` and cannot
  re-activate them. Gate it on `has_capability(roles, "catalog")`, with a test.
  Done (2026-09-23): `include_inactive=true` now follows `has_capability(roles, "catalog")`, so order_manager sees (and can re-activate) inactive products. 7 tests (negative control), browser 3/3. Found on the way: B6.16.
  → audit: [2026-09-23-b54b-include-inactive-catalog.md](audit/2026-09-23-b54b-include-inactive-catalog.md)

## Audit follow-ups (2026-09-22 full-stack audit)

- [x] **B6.1 Seed jobs run the additive DDL themselves** — `seed_auth` /
  `seed_products` / `seed_demo` call `startup_ddl()` like `seed_coupons` does, so
  compose's `db-init` no longer depends on the API container having booted first
  (it used to die on `invalid input value for enum app_role: "order_manager"` and
  abort the whole seed chain).
- [x] **B6.2 `GET /products` 500 for authenticated callers** — `_optional_admin`
  passed a role *string* into `AuthUser(roles=...)`, so `is_admin` raised
  `TypeError`. Replaced by the correct shared `OptionalUser` dependency.
- [x] **B6.3 Order lifecycle per spec [BE-05]** — status state machine
  (cancelled/delivered terminal, forward-only) and stock restoration on
  cancellation, for both the customer cancel and an admin status change.
- [x] **B6.4 Refund settlement is terminal** — re-settling a `refunded` request
  used to insert a second refund payment row; now 409.
- [x] **B6.5 Payment simulator gated** — `POST /orders/{id}/payment-complete`
  only works in simulation mode; with a real merchant id it is 409.
- [x] **B6.6 Authorization hardening** — no staff role from a stale JWT claim;
  `POST /payments/verify` is scoped to the session's owner; `GET /orders/{id}` is
  readable by staff with the `orders` capability (as its docstring promised).
- [x] **B6.7 Coupon code normalisation at redemption** — checkout matches codes
  case-insensitively, like `POST /coupons/validate` already did.
  → audit for B6.1–B6.7: [2026-09-22-full-stack-audit-and-fixes.md](audit/2026-09-22-full-stack-audit-and-fixes.md)
- [x] **B6.11 Optional mock dataset (`app.seed_mock`)** — idempotent, deterministic
  demo data so the admin screens are worth opening: 8 customers with staggered
  registration dates, 31 orders backdated over 47 days across every status, refund
  claims in all four [BE-03] states, 18 reviews from actual buyers, a size × colour
  variant matrix, a contact inbox and campaign coupons (one exhausted, one expired).
  Money, stock and payment rows are all internally consistent; not wired into the
  compose `db-init` chain (run it by hand).
- [x] **B6.12 `api_smoke.py` audit-log check ran before the mutation it asserts**
  — the "audit log records the admin order mutation" check sat 41 lines *above*
  the first `PATCH /orders/{id}`, so it only passed on a database that already had
  rows from an earlier run and always failed on a clean one. The block was moved
  after the mutations (assertion unchanged, not weakened).
  → audit for B6.11–B6.12: [2026-09-22-mock-dataset-seed.md](audit/2026-09-22-mock-dataset-seed.md)
- [x] **B6.8 Per-variant stock restoration on cancellation** — `order_items` now
  records `variant_id` (idempotent `CATALOG_DDL` column, written by checkout), so
  cancelling restores the variant row and the product aggregate in one
  transaction; legacy `NULL` rows still restore the aggregate only and a repeated
  cancellation is a no-op. Historical rows are not backfilled.
  → audit: [2026-09-22-b68-variant-stock-restore.md](audit/2026-09-22-b68-variant-stock-restore.md)
- [ ] **B6.8a Drop the redundant `information_schema` probe in `restore_stock()`**
  (`NEW-B68-1`, discovered during B6.8) — the column is now always created by
  `startup_ddl()`, so the per-cancellation existence check can go once every
  deployed stack has run the new DDL.
- [x] **B6.9 Stop swallowing errors in `POST /orders/{id}/refunds`** — the INSERT
  now catches `IntegrityError` and answers 409 only for SQLSTATE `23505`
  (`unique_violation`, i.e. the real duplicate); anything else is logged and
  re-raised, so a genuine database fault surfaces as a 500 instead of a false
  "a refund was already requested". Success/duplicate contracts are unchanged.
  → audit: [2026-09-22-b69-refund-exception-handling.md](audit/2026-09-22-b69-refund-exception-handling.md)
- [x] **B6.9a Narrow the remaining bare `except Exception` → 409 handlers**
  (`NEW-B69-1`, discovered during B6.9) — `routers/products.py` has four (variant
  and product CRUD) that report any failure as «این ترکیب سایز و رنگ قبلاً ثبت شده
  است»; `routers/storage.py` has two to review. Same fix shape as B6.9.
  Done (2026-09-23): only SQLSTATE 23505 keeps the duplicate answers in the four product/variant handlers and only MinIO/network errors keep the storage 502/`null`; everything else surfaces as a 500. Shared `services/db_errors.is_unique_violation`. 7 tests (negative control: 4 fail).
  → audit: [2026-09-23-b69a-narrow-catalog-storage-handlers.md](audit/2026-09-23-b69a-narrow-catalog-storage-handlers.md)
- [x] **F2.3 backend part — password reset tokens + endpoints** (task tracked in
  `frontend-tasks.md` F2.3): `password_reset_tokens`, `services/password_reset.py`,
  `POST /auth/password/forgot|reset`, `notifications.queue_private_email`.
  → audit: [2026-09-23-f23-forgot-password.md](audit/2026-09-23-f23-forgot-password.md)
- [x] **B6.14 A password reset does not end existing sessions** (`NEW-F23-1`,
  discovered during F2.3) — JWTs are stateless for 7 days, so a token stolen before
  a reset keeps working. Add `users.password_changed_at` (or a token version) set
  on reset and reject older `iat` in `get_current_user` / `get_optional_user`.
  Done (2026-09-23): `users.password_changed_at` + `_session_revoked()` in
  `app/auth.py` (whole-second cutoff). 6 tests, two-browser check, clean env.
  → audit: [2026-09-23-b614-reset-ends-sessions.md](audit/2026-09-23-b614-reset-ends-sessions.md)
- [x] **B6.16 Startup DDL deadlocks with in-flight requests on every restart**
  (`NEW-B54B-1`, discovered during B5.4b) — `startup_ddl()`'s `ALTER TABLE … ADD
  COLUMN IF NOT EXISTS` takes ACCESS EXCLUSIVE locks on hot tables at every boot and
  in every seed job; reproduced a `DeadlockDetectedError` → 500 on `GET /products`.
  Run only missing DDL (catalog check), advisory lock + `lock_timeout`; Rule 14.
  Done (2026-09-23): catalog-guarded startup DDL (runs only missing objects), advisory-lock serialization and a 10 s lock_timeout; the steady-state boot takes no table lock. Reproduction probe: deadlock → 300 requests / 12 reloads / 0 failures; clean env with an identical schema.
  → audit: [2026-09-23-b616-lock-free-startup-ddl.md](audit/2026-09-23-b616-lock-free-startup-ddl.md)
- [ ] **B6.15 `POST /coupons` accepts both discount kinds or neither** (`NEW-F516-1`,
  discovered during F5.16) — `CouponCreate._not_both` is a no-op stub; validate
  exactly one kind on create (422). The admin dialog already blocks both cases.
- [x] **B6.17 Storage upload refuses order_manager** (`NEW-ABFE04-1`, discovered
  during AB-FE-04) — `POST /storage/upload-url` uses `AdminUser` (`is_admin` =
  admin/super_admin only), so order_manager, who edits the catalog since B5.4b, gets
  403 and cannot add product images. Guard with `StaffCatalog`; fix the
  `require_admin` docstring ("any staff role passes" is wrong); per-role tests.
  Done (2026-09-23): `POST /storage/upload-url` now uses `StaffCatalog` (the product-edit guard): order_manager 200 (was 403), support/customer 403 with the Persian message, anonymous 401; `/storage/sign` unchanged; `require_admin` docstring corrected. 8 tests (negative control: 4 fail), smoke 235/0, browser upload as order_manager into MinIO. Integration + browser tested.
  → audit: [2026-09-23-b617-storage-upload-catalog-capability.md](audit/2026-09-23-b617-storage-upload-catalog-capability.md)
- [ ] **B6.18 Presigned image upload has no server-side size/type limit**
  (`NEW-ABFE04-2`, discovered during AB-FE-04) — the presigned PUT signs no type or
  length (200 kB of random bytes as `text/plain` accepted); the 5 MB / image rule is
  client-side only. Presigned POST policy (`content-length-range`, `image/*`) +
  multipart upload in `api.uploadImage` (keep progress).
- [x] **B6.13 The documented `pytest -q` silently skips every DB test**
  (`NEW-B21-3`, discovered during B2.1) — `test_addresses.py` (collected first) and
  three other modules `os.environ.setdefault("DATABASE_URL", "…u:p@…/db")` at
  import, `app.config.settings` is cached from that, and every live-DB module then
  skips as "no database reachable": `pytest -q` reports 77 passed / 60 skipped
  instead of 137 passed. Use one `conftest.py` default (the compose URL) or make
  the dummy-URL modules not import `app.config` first; AGENTS.md's verification
  command must actually run the integration tests.
  Done (2026-09-23): `tests/conftest.py` holds the one default (compose URL); the
  four dummy URLs are gone. Documented command: 79 passed / 72 skipped → 151 passed.
  → audit: [2026-09-23-b613-pytest-runs-db-tests.md](audit/2026-09-23-b613-pytest-runs-db-tests.md)
- [ ] **B6.10 Pagination for `GET /products` and `GET /admin/orders`** — both
  return the entire table; the spec's `[FE-02]` grid assumes server-side paging.
- [x] **AB-BE-03 Coupon max discount cap** (`[BE-02]`) — additive nullable
  `coupons.max_discount_cap INTEGER` (CHECK > 0) clamps a **percent-off**
  discount in `services/coupons.py::compute_discount`, the single point both
  `POST /coupons/validate` and checkout pass through, so the quote and the order
  can never disagree. Fixed `amount_off` coupons and NULL caps are unchanged, so
  every seeded coupon keeps its behaviour. Exposed in the coupon schemas and the
  admin CRUD (`PATCH` with `0` clears the ceiling); no admin UI field yet.
  → audit: [2026-09-22-abbe03-coupon-max-discount-cap.md](audit/2026-09-22-abbe03-coupon-max-discount-cap.md)

## Ideas (not scheduled)

- [ ] Redis cache for product catalog
- [ ] Rate limiting on checkout/payment endpoints
- [ ] Locale switch (i18n) for API error messages
