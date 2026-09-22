# Audit — 2026-09-22 — Full backlog and architecture audit (all four task/spec documents)

## Task

Ad-hoc user request: establish the **real remaining implementation backlog** for the
repository. Cross-check the actual codebase against all four task/spec documents —
`plan/backend-tasks.md`, `plan/frontend-tasks.md`, `plan/ADMIN-BACKEND_TASKS.md` and
`plan/ADMIN-FRONTEND_TASKS.md` — and produce one authoritative, prioritized backlog.

This is an **audit only**. No production code, task file, checkbox, rule file or spec
was modified. The user's explicit instruction: *"هیچ task یا checkbox پروژه را به خاطر
این audit تغییر نده"* — no task or checkbox was changed.

The downstream consumer of this file is another agent, which will derive the final
backlog and execution order from it. It is therefore written to be self-contained:
every status carries its own evidence and no section defers to chat context.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before the audit started, together with
`AGENTS.md`, `plan/RULES.md`, `plan/README.md`, the recent `plan/audit/*` files and
the live source trees.

**Followed** — the spec's Part B3 back-office module list, `[BE-01]`…`[BE-09]` and
`[FE-01]`…`[FE-08]` were used as the requirement set that the two ADMIN documents
restate, and each requirement was mapped to a live implementation or to a new
proposed task. Sections B0/B1 (UI/UX), B2 (directory conventions) and the Part C
backlog were used as the review lens.

**Deliberately not followed** — the spec's stack header and the ADMIN documents'
Supabase / RLS / `createServerFn` / RPC wording. Per Rule 0.2 the live repo wins:
this is FastAPI + SQLAlchemy + PostgreSQL with its own JWT, MinIO storage and
`src/lib/api.ts` as the sole data layer. Those clauses are recorded as `STALE` or
`SUPERSEDED` in **Documentation Drift** rather than implemented or deleted.

**Rule 4** — no status string (`paid/unpaid`, `pending/processing/shipped/delivered/
cancelled`, `succeeded/failed`, `SND-…`) and no cart money rule (۸۹٬۰۰۰ shipping,
free ≥ ۲٬۰۰۰٬۰۰۰ تومان) was touched or proposed for change anywhere in this audit.

---

# 1. Executive Summary

- **Existing tracked checkboxes (all four documents):** 135 — 61 backend, 74 frontend
- **Actually DONE:** 118
- **PARTIAL:** 4
- **TODO (genuinely remaining):** 11
- **BLOCKED (on a product/architecture decision):** 7
- **OBSOLETE:** 1
- **DUPLICATE:** 2
- **UNCLEAR:** 0
- **Newly proposed tasks derived from the two ADMIN specs:** 9 — 3 backend, 6 frontend
- **Total actionable backlog:** 24 (17 immediately actionable, 7 decision-gated)

Two of the 22 unticked checkboxes are already implemented (documentation drift), and
one shipped code path is contradicted by the schema:
`backend/app/services/order_lifecycle.py::restore_stock` contains a per-variant stock
restore branch that **can never execute**, because `order_items` has no `variant_id`
column and `services/checkout.py` never writes one. That is the single P0.

The backend is substantially ahead of the frontend. Three shipped backend
capabilities — `GET /admin/audit-logs` (B5.1), `PUT /admin/users/{id}/roles` (B5.4)
and `/admin/export/*.{csv,xlsx}` (B2.2) — have **zero** frontend entry point, not even
an `api.ts` client method.

---

# 2. Current Completion Snapshot

| Source | Total | Done | Partial | Todo | Blocked | Obsolete/Duplicate |
| ------ | ----: | ---: | ------: | ---: | ------: | -----------------: |
| `plan/backend-tasks.md` | 61 | 51 | 1 | 2 | 4 | 3 |
| `plan/frontend-tasks.md` | 74 | 67 | 2 | 3 | 2 | 0 |
| `plan/ADMIN-BACKEND_TASKS.md` (9 spec items) | 9 | 5 | 3 | 0 | 0 | 1 |
| `plan/ADMIN-FRONTEND_TASKS.md` (8 spec items) | 8 | 4 | 4 | 0 | 0 | 0 |
| **Total** | **152** | **127** | **10** | **5** | **6** | **4** |

The first two rows count individual checkboxes (135). The last two count the nine
`[BE-xx]` and eight `[FE-xx]` specification blocks, which are **not** checkbox tasks —
see Documentation Drift item 12. The per-source totals for the ADMIN rows therefore
overlap the checkbox rows by design: a spec block counted DONE there is DONE *because*
an existing checkbox task implemented it, and is not a separate unit of work.

Counting only real units of work: **135 tracked checkboxes + 9 newly derived tasks =
144**, of which **24 remain actionable**.

---

# 3. Audit Methodology / Evidence

## 3.1 What was inspected

- Governance: `AGENTS.md`, `plan/RULES.md`, `plan/README.md`, `plan/session-log.md`
- Specs: `design/SANDE_FULL_DEV_SPEC.md`, `plan/ADMIN-BACKEND_TASKS.md`,
  `plan/ADMIN-FRONTEND_TASKS.md`
- Recent audits, in particular `plan/audit/2026-09-22-full-stack-audit-and-fixes.md`,
  `2026-09-22-f25-pagination-everywhere.md`, `2026-09-22-b22-reports-exports.md`,
  `2026-09-22-b24-co-purchase-recommendations.md`,
  `2026-09-22-mock-dataset-seed.md`, `2026-09-21-backend-b54-granular-staff-roles.md`,
  `2026-09-21-backend-b51-audit-log.md`, `2026-09-21-backend-b53-refund-bank-tracking.md`
- Backend: every module under `backend/app/` (routers, services, `db.py`, `models.py`,
  `schemas.py`, `auth.py`, seeds) and `backend/tests/`
- Frontend: `vogue-vintage-vibes/src/` route tree, `src/lib/api.ts`, `src/lib/catalog.ts`,
  admin components, `package.json`
- Infra: `infra/docker-compose.yml`, `infra/initdb/02-public-schema.sql`,
  `infra/backend.Dockerfile`, `infra/frontend.Dockerfile`

## 3.2 Verified architecture (authoritative, Rule 0.2)

- **Backend:** FastAPI + async SQLAlchemy + PostgreSQL, own HS256 JWT
  (`app/security.py`, `app/auth.py`), roles resolved from the `user_roles` table via
  `app/services/roles.py` — never from the token claim. 15 routers under
  `app/routers/`, 14 services under `app/services/`.
- **Storage:** MinIO behind `POST /storage/upload-url` + `POST /storage/sign`
  (`app/routers/storage.py`). **No Supabase storage anywhere.**
- **Frontend:** TanStack Start / React, file-based routes under `src/routes/`,
  all HTTP through `src/lib/api.ts` (R7). `grep -rn "supabase" vogue-vintage-vibes/src`
  and `grep -ri supabase backend/app backend/tests` both return nothing.
- **No RLS, no Postgres RPC, no `createServerFn`.** Authorization is enforced in
  FastAPI dependencies (`require_staff(capability)` / `ROLE_CAPABILITIES`).

## 3.3 Method

Status was determined by tracing both sides of each contract, never by filename or
component-name matching:

- Frontend: `route/component → src/lib/api.ts → app/routers/* → app/services/* →
  app/models.py / raw SQL → Postgres`
- Backend: `router → auth dependency → service → model/DDL`

A backend endpoint with no frontend workflow is **not** counted as a complete feature,
and a UI whose backend contract is missing is **not** counted as complete either. Both
cases are recorded explicitly (AB-FE-02, F5.5, F5.6 are the three live examples).

## 3.4 Verification level of this audit (Rule 15)

**Inspected, not executed.** Every status below is verified by reading the current
source at the cited path; the audit did **not** run `pytest`, `ruff`,
`tests/api_smoke.py`, `bun run lint/build` or the Docker stack in this session.
Therefore:

- `implemented` — the code exists and was read. Used throughout.
- `verified` — claimed **only** where a prior audit file documents an executed check,
  and that audit is cited by name.
- `not verified` — the runtime behaviour of B6.8 (the P0) was **not** reproduced on a
  live stack; it is inferred from the schema and the INSERT statement, which is
  conclusive at the code level but has no runtime proof in this session.

Quoted figures — 39 unit tests, ruff clean, 173 smoke checks, clean `tsc`/`lint`/`build` —
come from `plan/audit/2026-09-22-full-stack-audit-and-fixes.md` and are **not** re-run
here. Local counts confirm 39 `def test_` across the four test modules
(`test_addresses.py` 2, `test_pricing_and_coupons.py` 19,
`test_availability_and_filters.py` 14, `test_variants.py` 4).

---

# 4. Per-task status — `plan/backend-tasks.md`

61 checkboxes. Classification and evidence for every one.

## Milestone B1 — Core service (9 items)

| ID | Doc | Status | Evidence |
|----|-----|--------|----------|
| B1.1 Scaffold FastAPI | `[x]` | **DONE** | `backend/pyproject.toml`, `app/main.py`, `app/config.py` |
| B1.2 DB layer | `[x]` | **DONE** | `app/db.py` (engine + additive DDL blocks), `app/models.py` |
| B1.3 JWT auth + roles | `[x]` | **DONE** (superseded in scope by B1.9/B5.4) | `app/security.py`, `app/auth.py`, `app/services/roles.py`. The title still says "Supabase JWT" — see Drift 13 |
| B1.4 Real coupon system | `[x]` | **DONE** | `COUPON_DDL` `app/db.py:40-70`; `app/routers/coupons.py`; `app/services/coupons.py`; `app/seed_coupons.py` |
| B1.5 Transactional stock decrement | `[x]` | **DONE** (product aggregate + variant) | `app/services/checkout.py:205-245` — guarded `stock >= :qty` UPDATE, `rowcount != 1` → `CheckoutError` |
| B1.6 Zarinpal gateway | `[x]` | **DONE** (simulation mode only in this env) | `app/routers/payments.py`, `app/services/payments.py::simulation_mode` |
| B1.7 Product search | `[x]` | **DONE** | `app/routers/search.py`, `app/services/search.py` |
| B1.8 Tests + lint clean | `[x]` | **DONE** (verified by the 2026-09-22 full-stack audit, not re-run here) | `backend/tests/` — 39 `def test_` |
| B1.9 Sole backend, no Supabase | `[x]` | **DONE** | 15 routers under `app/routers/`; `grep -ri supabase backend/app` → nothing |

## Milestone B2 — Remaining Part-7 features (7 items + B6.1 state machine listed here)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| B6.1 Order state machine (listed in B2) | `[x]` | **DONE** — but see Drift 2, the ID is used twice | `app/services/order_lifecycle.py::ALLOWED_STATUS_TRANSITIONS`, `assert_transition`, `cancel_order_tx`; enforced in `app/routers/orders.py` |
| B2.1 SMS/email notifications | `[ ]` | **BLOCKED** (decision D2) | No provider module, no SMTP/SMS dependency in `pyproject.toml`. Blocks F2.3, B2.5, B4.13 |
| B2.2 Reports & exports | `[x]` | **DONE** (backend) | `app/routers/exports.py` — `/orders.csv`, `/orders.xlsx`, `/products.csv`, `/products.xlsx`, `/report`; `_range_or_400` handles `from`/`to`; `StaffOrders` guard. **Frontend entry point missing → AB-FE-02** |
| B2.2a CSV product import | `[ ]` | **BLOCKED** (decision D3 — overwrite/skip policy + idempotency key) | No import route in `app/routers/exports.py` or elsewhere |
| B2.3 PDF invoices | `[ ]` | **TODO** (P3) | No reportlab/weasyprint in `pyproject.toml`. F4.4's `@media print` A4 invoice covers the practical need |
| B2.4 Recommendation engine | `[x]` | **DONE** | `app/services/recommendations.py`; `co_purchases` refreshed in `app/services/checkout.py:248-251` |
| B2.5 Webhooks + background jobs | `[ ]` | **BLOCKED** (decision D2 for the notification half) | No APScheduler dependency, no scheduler wiring in `app/main.py` |
| B2.6 Coupon admin UI support | `[ ]` | **OBSOLETE** | Its own body says "nothing to build in Python… superseded by B1.9". `/coupons` CRUD exists and `/admin/coupons` (F4.5) consumes it. See Drift 3 |

## Milestone B3 — Debt from the sole-service rewrite (13 items)

| ID | Doc | Status | Evidence |
|----|-----|--------|----------|
| B3.1 `DATABASE_URL` examples | `[x]` | **DONE** | `backend/.env.example`, `infra/.env.example`, `infra/docker-compose.yml` use `postgresql+asyncpg://` |
| B3.2 Refresh `backend/README.md` | `[x]` | **DONE** | `backend/README.md` documents the sole-backend architecture |
| B3.3 Refresh `infra/README.md` | `[x]` | **DONE** | `infra/README.md` |
| B3.4 Clean stale Supabase wording in code | `[x]` | **DONE** | `grep -ri supabase backend/app backend/tests` → nothing |
| B3.5 Tests for the new routers | `[x]` | **PARTIAL** (self-declared) | `tests/test_addresses.py`, `tests/test_variants.py`, `tests/api_smoke.py`. The task text itself states the pytest DB fixture for router-level unit tests is still open; smoke needs a running server. Left as-is — the checkbox is honest about its own gap |
| B3.6 Stack runs in Docker | `[x]` | **DONE** (verified by `2026-09-19-docker-stack-up-and-runtime-fixes.md`) | `infra/docker-compose.yml`, quay.io MinIO images |
| B3.7 Persist the payment authority | `[x]` | **DONE** | `payments.authority` column + index in `app/db.py`; `app/services/payments.py::verify_and_finalize` |
| B3.8 `HTTPException` double-`detail` | `[x]` | **DONE** | `app/routers/checkout.py`, `app/routers/payments.py` pass one `detail` object |
| B3.9 `POST /contact` + admin inbox | `[x]` | **DONE** | `app/routers/contact.py` — public POST, `GET/DELETE /admin/contact-messages` |
| B3.10 Address book single default + PATCH | `[x]` | **DONE** | `app/routers/addresses.py`; `tests/test_addresses.py` |
| B3.11 Spam guard for `POST /contact` | `[ ]` | **BLOCKED** (decision D1 — throttle vs honeypot vs captcha) | `app/routers/contact.py:34-50` is an unauthenticated unbounded INSERT; no rate limit, honeypot or captcha anywhere in the app |
| B3.12 Shipment tracking code | `[x]` | **DONE** | `TRACKING_DDL` in `app/db.py`; `PATCH /orders/{id}` accepts `tracking_code` (`app/routers/orders.py::OrderPatch`) |
| B3.13 Mark a contact message answered | `[x]` | **DONE** | `PATCH /admin/contact-messages/{id}`, `ContactMessageStatusIn` in `app/schemas.py` |

## Milestone B4 — Catalog & Products backend (13 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| B4.1 Product merchandising | `[x]` | **DONE** | `CATALOG_DDL` in `app/db.py`; `tags`, `badge`, `availability`, `available_at`, `low_stock_threshold`, `avg_rating`, `review_count` |
| B4.2 Catalog filters + sort | `[x]` | **DONE** | `app/routers/products.py:126-203`; `app/services/catalog_filters.py` |
| B4.3 Variants with per-combination stock | `[x]` | **DONE** | `product_variants` DDL `app/db.py:92-108` with `UNIQUE (product_id, size, color)`; `app/services/variants.py`; variant CRUD `app/routers/products.py:340-460` |
| B4.4 Reviews & ratings + seller replies | `[x]` | **DONE** | `product_reviews` DDL; `app/routers/reviews.py` |
| B4.5 Search autocomplete + history | `[x]` | **DONE** | `GET /search/suggest`, `GET/DELETE /search/history` in `app/routers/search.py` |
| B4.6 Related / recommended / compare / recently viewed | `[x]` | **DONE** | `app/routers/products.py`, `app/services/recommendations.py` |
| B4.7 Low-stock inventory | `[x]` | **DONE** | `GET /admin/inventory` `app/routers/admin.py:357`, `/inventory/low-stock` `:393` |
| B4.8 Product model dimension | `[ ]` | **BLOCKED** (decision D7) | Variants are size × color only (`UNIQUE (product_id, size, color)`). A third axis is a catalogue policy call |
| B4.9 Stock reservation with TTL | `[ ]` | **BLOCKED** (decision D5) | Stock is decremented at order creation (`app/services/checkout.py:205`), not reserved during checkout. Also the unimplemented half of `[BE-05]` |
| B4.10 Search matches product tags | `[x]` | **DONE** | `app/services/search.py` ranks name > category > tag > description; `app/seed_products.py` tags all 20 |
| B4.11 Enforce `availability` in stock-check and checkout | `[x]` | **DONE** | `app/services/availability.py::availability_issue`, applied in `POST /stock/check` and checkout |
| B4.12 Multi-value catalog filters | `[x]` | **DONE** | `app/services/catalog_filters.py::split_multi` |
| B4.13 Preorder fulfilment flag | `[ ]` | **BLOCKED** (decision D4, and D2 for the notification half) | `preorder` is deliberately blocked by `availability_issue()` per an explicit user decision; `orders` has no preorder marker |

## Milestone B5 — Spec-only backend work (6 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| B5.1 Admin audit log | `[x]` | **DONE** (backend) | `AUDIT_DDL` in `app/db.py`; `app/services/audit.py::record_audit`; `GET /admin/audit-logs` `app/routers/admin.py:270`. **No UI → F5.5** |
| B5.1a Audit IP capture | `[x]` | **DONE** | `client_ip_ctx` + `capture_client_ip` middleware in `app/main.py`, consumed by `record_audit` |
| B5.1b Audit tamper-resistance at the DB level | `[ ]` | **TODO** (P2) | `grep -rn REVOKE backend/ infra/` → **no match**. The app role can UPDATE/DELETE `audit_logs`, contradicting `[BE-04]`'s "tamper-resistant" goal |
| B5.2 KPI aggregation endpoint | `[x]` | **DONE** | `GET /admin/kpis` `app/routers/admin.py:128-230` — gross/net/paidOrders/AOV, daily series, status breakdown, previous-window deltas |
| B5.3 Refund bank-tracking fields | `[x]` | **DONE** | `REFUND_DDL` in `app/db.py`; `PATCH /refunds/{id}` requires `bank_tracking_code` when settling (`app/routers/orders.py:334-338`) |
| B5.4 Granular staff roles | `[x]` | **DONE** | `ROLE_DDL`; `require_staff(capability)` + `ROLE_CAPABILITIES` in `app/services/roles.py`; `PUT /admin/users/{id}/roles` `app/routers/admin.py:485`. **No UI → F5.6** |

## Audit follow-ups from 2026-09-22 (12 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| B6.1 Seed jobs run the additive DDL | `[x]` | **DONE** — **DUPLICATE ID** with the B2-section B6.1 | `app/seed_auth.py`, `app/seed_products.py`, `app/seed_demo.py` call `startup_ddl()`. See Drift 2 |
| B6.2 `GET /products` 500 for authenticated callers | `[x]` | **DONE** | `app/routers/products.py` uses the shared `OptionalUser`; the broken `_optional_admin` is gone |
| B6.3 Order lifecycle per `[BE-05]` | `[x]` | **DONE** — **DUPLICATE** of the B2-section B6.1 | Same implementation: `app/services/order_lifecycle.py`. See Drift 2 |
| B6.4 Refund settlement is terminal | `[x]` | **DONE** | `app/routers/orders.py:340-355` — `previous_status == "refunded"` → 409 |
| B6.5 Payment simulator gated | `[x]` | **DONE** | `simulation_mode()` gate on `POST /orders/{id}/payment-complete` |
| B6.6 Authorization hardening | `[x]` | **DONE** | `app/auth.py` takes no staff role from the token claim; `verify_and_finalize(user_id=…)` ownership scope; staff single-order read |
| B6.7 Coupon code normalisation at redemption | `[x]` | **DONE** | `app/services/coupons.py::get_coupon_for_update` normalises like `POST /coupons/validate` |
| B6.8 Per-variant stock restoration on cancellation | `[ ]` | **TODO — P0** | See §10. `infra/initdb/02-public-schema.sql:107-118` has no `variant_id`; no additive DDL adds it; `app/services/checkout.py:180-198` does not insert it; `app/services/order_lifecycle.py:63-94` guards on an `information_schema` probe that is always false |
| B6.9 Stop swallowing errors in `POST /orders/{id}/refunds` | `[ ]` | **TODO — P1** | `app/routers/orders.py:299-321` — bare `except Exception` → 409 "already requested" for every failure |
| B6.10 Pagination for `GET /products` and `GET /admin/orders` | `[ ]` | **DONE — documentation drift** | Both paginate: `app/routers/products.py:126-203` and `app/routers/admin.py:330-353`, via `app/services/pagination.py`. Implemented by F2.5; the backend checkbox was never ticked. See Drift 1 |
| B6.11 Optional mock dataset | `[x]` | **DONE** | `app/seed_mock.py` — 8 customers, 31 orders, refunds in all four states, 18 reviews, variant matrix, coupons |
| B6.12 `api_smoke.py` audit-log check ordering | `[x]` | **DONE** | Assertion moved after the mutations in `tests/api_smoke.py` |

**Ideas (not scheduled, not counted in the 61):** Redis catalog cache; rate limiting on
checkout/payment; locale switch for API error messages. The rate-limiting idea overlaps
decision D1 and should be decided with it.

---

# 5. Per-task status — `plan/frontend-tasks.md`

74 checkboxes.

## Milestone F1 — Wire the store to the Python backend (16 items)

| ID | Doc | Status | Evidence |
|----|-----|--------|----------|
| F1.0 Backend endpoints for the switch | `[x]` | **DONE** | `PATCH /auth/me`, `GET /payments/mine` |
| F1.0b Catalog seed | `[x]` | **DONE** | `app/seed_products.py`, `app/seed_demo.py`, wired into compose `db-init` |
| F1.1 Backend client module | `[x]` | **DONE** | `src/lib/api.ts` — token storage, `request()`, `ApiError`, typed method per endpoint |
| F1.1b Auth/session layer | `[x]` | **DONE** | `src/lib/auth.tsx`, `src/routes/_authenticated/route.tsx`, `src/routes/auth.tsx` |
| F1.1c Catalog + images | `[x]` | **DONE** | `src/lib/catalog.ts`, `src/components/admin/ProductImageManager.tsx` |
| F1.2 Real coupons in cart | `[x]` | **DONE** | `src/routes/cart.tsx` → `POST /coupons/validate`; code (never the amount) passed in `sessionStorage` |
| F1.3 Checkout through backend | `[x]` | **DONE** | `src/routes/checkout.tsx` → `POST /checkout`; `stock_conflict` surfaced |
| F1.4 Payment page on the backend | `[x]` | **DONE** (simulated gateway) | `src/routes/_authenticated/payment.$orderId.tsx`. Real Zarinpal redirect stays open as A1 |
| F1.5a Account routes | `[x]` | **DONE** | `src/routes/_authenticated/account.*.tsx` |
| F1.5b Admin routes | `[x]` | **DONE** | `src/routes/_authenticated/admin.*.tsx` |
| F1.8 Remove Supabase from the frontend | `[x]` | **DONE** | No `src/integrations/*`; no `@supabase/supabase-js` import |
| F1.10 End-to-end run on the Docker stack | `[x]` | **DONE** (verified by `2026-09-19-e2e-flow-docker.md`) | — |
| F1.5 Search bar | `[x]` | **DONE** via F3.1 | `src/components/HeaderSearch.tsx` |
| F1.6 Live stock in product page & cart | `[x]` | **DONE** via F3.2/F3.5 | `src/components/product/VariantPicker.tsx`, `src/lib/stock-issues.ts` |
| F1.7 Stock decrement shown to admin | `[x]` | **DONE** via F3.6 | `src/routes/_authenticated/admin.inventory.tsx` |
| F1.9 Lovable preview tooling | `[ ]` | **TODO** (P3) | `src/lib/lovable-error-reporting.ts`, `src/lib/error-capture.ts` kept; revisit when the app leaves Lovable |

**A1 open decisions (not checkboxes):** real Zarinpal redirect flow; Google/OAuth login
(removed with Supabase, needs a backend OAuth flow). Both remain open; neither is
counted in the 74.

## Milestone F2 — Gaps from FEATURES.md part 6 (9 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| F2.1 Contact form persistence | `[x]` | **DONE** | `src/routes/contact.tsx` → `api.contact()` |
| F2.1b Admin contact inbox | `[x]` | **DONE** | `src/routes/_authenticated/admin.messages.tsx` — filter chips, Jalali dates, mark answered, delete |
| F2.3 Forgot password | `[ ]` | **BLOCKED** (decision D2) | `grep -n "@router" app/routers/auth.py` → only `/signup`, `/login`, `PATCH /me`, `GET /me`. **No reset endpoint exists**, and none is tracked in `backend-tasks.md` yet. Needs a mail transport first |
| F2.4 Admin refund-requests page | `[x]` | **DONE** | `src/routes/_authenticated/admin.refunds.tsx` + `RefundActionDialog`; bank code required to settle |
| F2.5 Pagination for shop & admin lists | `[x]` | **DONE** (but see AB-FE-05) | `src/components/Pager.tsx` used by `shop.tsx`, `admin.orders.tsx`, `admin.users.tsx`, `admin.messages.tsx`, `admin.reviews.tsx`, `account.orders.tsx`. **`admin.products.tsx` is not in that list** |
| F2.6 Charts for admin dashboard | `[x]` | **DONE** | `src/routes/_authenticated/admin.index.tsx` — range selector, 4 KPI cards, recharts area chart, status donut, urgent-actions callout |
| F2.7 Default address in checkout | `[x]` | **DONE** | `src/routes/checkout.tsx`, `account.addresses.tsx` |
| F2.7b Edit a saved address | `[x]` | **DONE** | Shared `AddressFields`, fields-only PATCH |
| F2.8 Shipment tracking number | `[x]` | **DONE** | `admin.orders.tsx` input → `PATCH /orders/{id}`; customer sees it in the stepper box |

## Milestone F3 — Catalog & Products UI (36 items)

| Group | Items | Status | Evidence / what is missing |
|-------|------:|--------|----------------------------|
| F3.0 API client + types | 6 | **DONE** (all 6) | `src/lib/api.ts` exports `Availability`, `ProductBadge`, `ProductSort`, `ProductListParams`, `ProductVariant(-Input)`, `Review`, `ReviewList`, `SearchSuggestion`, `InventorySummary`, `LowStockReport`, … |
| F3.1 Search | 4 | **DONE** (all 4) | `HeaderSearch.tsx`, `shop.tsx` `?q=`, `src/lib/catalog.ts::searchQuery` |
| F3.2 Product page | 9 | **DONE** (all 9) | `src/routes/product.$id.tsx`, `VariantPicker.tsx`, `ReviewsSection.tsx`, `ProductRail.tsx`, `src/lib/variants.ts` |
| F3.3 Catalog listing / shop | 6 | **DONE** (all 6) | `shop.tsx` server-side filters via `validateSearch`; `ProductCard.tsx` rating; `src/lib/compare.tsx` + `CompareBar.tsx` + `src/routes/compare.tsx` |
| F3.4 Recently viewed | 1 done | **DONE** | `RecentlyViewedRail.tsx` |
| F3.4b Guest recently-viewed | `[ ]` | **BLOCKED** (decision D7 — merge-on-sign-in semantics) | `GET /recently-viewed` requires auth and has no DELETE |
| F3.5 Cart stock re-validation | 1 done | **DONE** | `api.stockCheck()` posts the bare array; query keyed on the full cart signature; checkout blocked while `ok: false` |
| F3.5b Re-check on focus | `[ ]` | **TODO** (P2, low risk) | Stale UI only — checkout re-validates server-side |
| F3.6 Admin | 4 | **DONE** (all 4) | `admin.products.tsx` merchandising fields; `VariantEditor.tsx`; `admin.inventory.tsx`; `admin.reviews.tsx` |
| F3.7 Supersedes F1/F2 items | 3 | **DONE** (all 3) | F1.5→F3.1, F1.6→F3.2/F3.5, F2.2→F3.2/F3.6 |

## Milestone F4 — Spec-aligned admin UI (5 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| F4.1 Token-driven status badges | `[x]` | **DONE** | `src/components/StatusBadge.tsx` |
| F4.2 Admin shell | `[x]` | **PARTIAL** (self-declared) | `src/routes/_authenticated/admin.tsx` — sidebar, mobile Sheet, quick search, role badge, logout, `ROLE_TAB_KEYS` gating. Its own audit defers breadcrumbs, avatar dropdown, collapse toggle and `Cmd+K`; confirmed still absent (`grep -rn metaKey src/` hits only `ui/sidebar.tsx`; `CommandDialog` in `ui/command.tsx` is unused) → **AB-FE-01** |
| F4.3 Reusable admin data grid | `[ ]` | **BLOCKED** (decision D8 — install `@tanstack/react-table`) | Not in `vogue-vintage-vibes/package.json`. `grep -rn Checkbox src/routes/_authenticated/` → nothing, so `[FE-02]`'s floating bulk-action bar has no counterpart either |
| F4.4 Order detail drawer + invoice printing | `[x]` | **DONE** | `src/components/admin/OrderDetailDrawer.tsx` + the `styles.css` `@media print` block |
| F4.5 Coupons manager | `[x]` | **DONE** | `src/routes/_authenticated/admin.coupons.tsx` — ticket cards, usage bar, Switch toggle, create/edit dialog, `DELETE /coupons/{id}` |

## Audit follow-ups from 2026-09-22 (8 items)

| ID | Doc | Status | Evidence / what is missing |
|----|-----|--------|----------------------------|
| F5.1 Admin route role guard | `[x]` | **DONE** | `admin.tsx` maps path → tab and renders a Persian permission notice |
| F5.2 Persian 404 and error boundary | `[x]` | **DONE** | `src/routes/__root.tsx` |
| F5.3 Staff role labels in `/admin/users` | `[x]` | **DONE** | `ROLE_LABELS` map in `admin.users.tsx:8-63` |
| F5.4 `bun run lint` green | `[x]` | **DONE** (verified by the 2026-09-22 full-stack audit) | — |
| F5.5 Audit-log viewer | `[ ]` | **TODO — P1** | `grep -n "audit" src/lib/api.ts` → **no match**. No client method, no route. `GET /admin/audit-logs` has no reader |
| F5.6 Role management UI | `[ ]` | **TODO — P1** | `admin.users.tsx` only renders `user.roles` (lines 61-63); no mutation, no `api.ts` method for `PUT /admin/users/{id}/roles` |
| F5.7 Split the admin chart bundle | `[ ]` | **PARTIAL / mis-stated** | `recharts ^2.15.4` is a direct dependency (`package.json:61`), but **lodash is not in `package.json`** — it is transitive. Re-measure before acting; the actionable half is route-level lazy loading of `/admin` |
| F5.8 `/shop` fetches the catalog twice | `[ ]` | **TODO** (P2) | Confirmed: `shop.tsx:198` `useCatalog()` (facets, price bounds) **and** `shop.tsx:219` `api.products({...filters, page, page_size: 12})` |

---

# 6. Per-task status — `plan/ADMIN-BACKEND_TASKS.md`

This file is a **specification**, not a tracked task list (no checkboxes, no audit
links — Drift 12). Each `[BE-xx]` block is mapped below. **No duplicate task was
created where an existing implementation already satisfies the requirement.**

### `[BE-01]` Product Variants Matrix & Inventory Management — **PARTIAL**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `product_variants` table | **DONE** → B4.3 | `app/db.py:92-105` |
| `UNIQUE (product_id, size, color_name)` | **DONE** | `UNIQUE (product_id, size, color)` in the same DDL |
| Index on `product_id` | **DONE** | `product_variants_product_idx`, `app/db.py:106-107` |
| `sku` unique + indexed | **TODO** → **AB-BE-02** | `sku TEXT` is nullable with **no unique constraint and no index** (`app/db.py:97`) |
| `color_hex` | **TODO** → **AB-BE-02** | Only `color TEXT` exists |
| `price_override` | **TODO** → **AB-BE-02** | Absent; `app/services/pricing.py` prices from `products.price` only |
| `inventory_logs` table | **TODO** → **AB-BE-01** | `grep -rn inventory_logs backend/ infra/` → **nothing**. No stock ledger of any kind |
| FK to `auth.users.id` | **SUPERSEDED** | This repo has `public.users`; there is no `auth` schema |

### `[BE-02]` Promotional Engine & Coupons — **PARTIAL**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `coupons` table, unique code | **DONE** → B1.4 | `app/db.py:44-58` |
| Case-insensitive code handling | **DONE** → B6.7 | `app/services/coupons.py` normalises at validate **and** redemption |
| `discount_type`/`value` | **DONE** (different shape) | `percent_off` XOR `amount_off` with CHECK constraints — equivalent, not a gap |
| `min_order_amount` | **DONE** | `min_subtotal` |
| `usage_limit` / `used_count` | **DONE** | `max_uses`, `used_count`, plus `max_uses_per_user` (beyond spec) |
| `starts_at` / `expires_at` / `is_active` | **DONE** | `starts_at`, `expires_at`, `active` |
| `coupon_usages` | **DONE** | `coupon_redemptions` with `UNIQUE (coupon_id, order_id)` |
| Race condition on `usage_limit` | **DONE** | `app/services/coupons.py:52` `SELECT * FROM public.coupons WHERE code = :code FOR UPDATE`, increment at `:107`, inside the checkout transaction |
| `max_discount_cap` | **TODO** → **AB-BE-03** | **Absent.** A `percent_off` coupon has no ceiling on a high-value cart |

### `[BE-03]` Returns & Refund Requests Processing — **DONE**

`refund_requests` with `amount`, `reason`, `status`, `bank_tracking_code`,
`admin_notes` (`admin_note`), `resolved_by`, `resolved_at` — all present via
`REFUND_DDL` (`app/db.py`) and B5.3. Lifecycle in `app/routers/orders.py:325-410`,
terminal settlement via B6.4.

- **RLS policies clause → SUPERSEDED.** There is no RLS. Ownership is enforced in
  `_fetch_order(session, id, user_id=user.id)` and `require_staff("refunds")`. The
  2026-09-22 full-stack audit records IDOR probes on refunds returning 404/403.
- **`[FE-06]`'s customer IBAN/Sheba panel has no backing column** → decision D6.

### `[BE-04]` Admin RBAC & Audit Logging — **PARTIAL**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `user_roles` with `super_admin`/`order_manager`/`support` | **DONE** → B5.4 | `ROLE_DDL`; `app/services/roles.py::ROLE_CAPABILITIES` |
| Roles never on the user row | **DONE** → B6.6 | `app/auth.py` takes no staff role from the JWT claim |
| `audit_logs` table with old/new values + IP | **DONE** → B5.1 + B5.1a | `AUDIT_DDL`; `app/services/audit.py::record_audit`; `client_ip_ctx` |
| **Tamper-resistant** | **TODO** → B5.1b | No `REVOKE` anywhere; the app role can UPDATE/DELETE `audit_logs` |
| Viewable | **TODO** → F5.5 | Endpoint exists, no UI |

### `[BE-05]` Order Lifecycle Management RPC — **PARTIAL**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Validate state-machine transitions | **DONE** → B6.1/B6.3 | `ALLOWED_STATUS_TRANSITIONS`, `assert_transition` |
| `trackingCode` parameter | **DONE** → B3.12 | `OrderPatch.tracking_code` |
| `internalNote` parameter | **DONE** | `orders.note` column (`infra/initdb/02-public-schema.sql:100`); `RefundResolveIn.admin_note` for refunds |
| Insert into `audit_logs` | **DONE** → B5.1 | `record_audit` on every privileged order mutation |
| Atomic transaction | **DONE** | `cancel_order_tx` runs on the caller's transaction |
| Restore stock on cancellation | **PARTIAL** → **B6.8 (P0)** | Product aggregate only; the per-variant branch is unreachable |
| **Reserve/commit stock on payment success** | **BLOCKED** → B4.9 (decision D5) | Stock is decremented at order creation, never reserved |
| "RPC" / `updateOrderStatus` signature | **STALE** | Implemented as `PATCH /orders/{id}`; there are no Postgres RPCs |

### `[BE-06]` Coupon Validation Engine — **DONE** (except the cap)

All five validation rules are implemented in `app/services/coupons.py`: existence +
`active` (`:52-70`), date window, `min_subtotal`, global `max_uses` (`:77`) and the
per-user cap (`:79`, stricter than the spec's "max 1 use"). Response shape is the
sanitized payload + computed discount from `app/services/pricing.py`.
→ covered by **B1.4 + B6.7**; the missing ceiling is **AB-BE-03**, not a new engine.

### `[BE-07]` SMS Notification Gateway — **TODO** → **covered by B2.1**, BLOCKED on D2

No new task. Every trigger the spec lists (status → `processing`/`shipped` with the
postal code, refund approved/settled, ops alert on high-value orders and new refund
claims) belongs inside B2.1's scope.

### `[BE-08]` Orders & Financial Data Export Service — **DONE** → **covered by B2.2**

`app/routers/exports.py` implements the full signature: `fromDate`/`toDate`
(`_range_or_400`), `status?`, and both formats. Output carries shipping details, SKU
breakdown, payment reference and the discount split; RFC-4178 CSV and RFC-6266
filenames; `StaffOrders` guard. **The only gap is the UI entry point → AB-FE-02.**
The "RPC / server function" wording is STALE.

### `[BE-09]` Dashboard Aggregations — **DONE** → **covered by B5.2** (+ F2.6)

`GET /admin/kpis?range=today|7d|30d|all` returns gross, net, paid order count, AOV,
pending refunds and low-stock count, plus the daily series, status breakdown and
previous-window deltas the spec does not even ask for.
**One mismatch:** the spec hardcodes "Low-Stock Alert Count (< 5 units)"; the repo uses
a per-product `low_stock_threshold` (B4.1), which is strictly better → decision D9
(retire the hardcoded 5 in the spec rather than regress the implementation).

---

# 7. Per-task status — `plan/ADMIN-FRONTEND_TASKS.md`

Also a specification, not a task list.

### Section 0 — Design System & Visual Guidelines — **DONE**

RTL, Cormorant Garamond + Persian sans, `formatPrice` thousand separators, the
terracotta/sage/sand token set and the status colour coding are all implemented and
documented in `vogue-vintage-vibes/DESIGN_SYSTEM.md`; the status coding specifically
shipped as F4.1 (`src/components/StatusBadge.tsx`). Skeleton loaders and Sonner toasts
are in use. No new task.

### `[FE-01]` Responsive Admin Layout & Sidebar — **PARTIAL** → **covered by F4.2 + F5.1**

Implemented: sidebar with 18px Lucide icons and the terracotta active edge, mobile
Sheet, role-based menu filtering, KPI-fed counter badges on orders/refunds, quick
search, role badge, sign-out, and (F5.1) the direct-URL permission guard.
Missing: breadcrumbs, avatar dropdown, sidebar collapse toggle, `Cmd+K` palette,
storefront preview link → **AB-FE-01**.

### `[FE-02]` Editorial Data Table Component — **PARTIAL** → **covered by F4.3** (blocked)

Implemented piecemeal: server-side pagination exists per list (F2.5, `Pager.tsx`),
search and filter chips exist on individual admin routes.
Missing: the reusable `AdminDataTable`, TanStack Table v8 (not installed), sorting
indicators, the floating bulk-action bar (no `Checkbox` in any admin route), and the
CSV export trigger → the export trigger is split out as **AB-FE-02** so it is not
blocked behind the dependency decision.

### `[FE-03]` Executive KPI Dashboard — **DONE** → **covered by F2.6**

Bento grid of 4 KPI cards with delta badges, recharts gradient area chart, status
donut with legend, urgent-actions widget, TanStack Query caching. No new task.

### `[FE-04]` Product & Inventory Catalog Management — **PARTIAL** → **covered by F3.6**

Implemented: merchandising fields, `VariantEditor.tsx` (create/patch stock/delete),
inventory + low-stock screen, thumbnail list with availability/badge/low-stock chips.
Missing:
- Two-column editor layout, colour **swatch picker**, React Hook Form + Zod
  (`grep -n "zod\|react-hook-form" admin.products.tsx` → no match; state is hand-rolled)
  → **AB-FE-03**
- Image gallery: drag-and-drop zone, reorderable previews, primary-image star, hover
  delete. `ProductImageManager.tsx` validates MIME type and uploads only
  (`grep -n "drag\|onDrop\|reorder\|primary\|star"` → only the MIME check at `:48`)
  → **AB-FE-04**
- Pagination on `/admin/products` → **AB-FE-05**
- "Direct Supabase storage bucket upload" → **STALE**; uploads go through
  `POST /storage/upload-url` to MinIO

### `[FE-05]` Order Processing & Detail Drawer — **DONE** → **covered by F4.4**

Left-side wide Sheet, status stepper, customer/shipping card with copy, itemised
breakdown with size/color chips, postal tracking input, `@media print` A4 invoice.
The spec's stepper labels (Placed ➔ Paid ➔ Processing ➔ Shipped) were adapted to the
frozen Rule-4 statuses (`pending → processing → shipped → delivered`) — a deliberate,
already-audited deviation, recorded in Drift 10 so it is not reopened as a defect.
"TanStack server function mutations" → **STALE**; mutations go through `src/lib/api.ts`.

### `[FE-06]` Refund & Returns Processing Center — **PARTIAL** → **covered by F2.4**

Implemented: status-grouped cards, `StatusBadge` tones, resolution modal with the
mandatory bank/SATNA tracking input, optional note, approve-settle / reject, automatic
order payment-status sync, cache refresh.
Missing: the customer IBAN/Sheba monospace panel — **there is no column for it** in
`refund_requests` → **decision D6**, not a task yet.
`resolveRefundRequest` "server function" → **STALE**; it is `PATCH /refunds/{id}`.

### `[FE-07]` Promotion & Discount Campaign Manager — **DONE** → **covered by F4.5**

Ticket-style cards, bold discount metric, active toggle Switch, usage progress bar,
date pickers (native inputs — the Persian calendar dependency was declined, recorded in
that task's audit), code uniqueness, expiration badges. No new task.

### `[FE-08]` Customer 360° Profile & CRM — **PARTIAL**

Implemented: the users list with staff role labels (F5.3) and pagination (F2.5).
Missing, split in two:
- **Role management trigger with two-step confirmation** → already tracked as **F5.6**
  (do **not** create a new task)
- Avatar/initials, customer tier badge (New/VIP/Wholesale), LTV metric, average days
  between purchases, and the drawer tabs for Order History / Saved Addresses /
  Wishlist → **AB-FE-06** (tier thresholds are decision D7)

---

# 8. Product / Architecture Decisions Required

Code should not be written for these until the decision is made. The decision is the
user's; this audit does not make it.

### D1 — Contact-form abuse control
- **Decision:** per-IP throttle (needs a shared counter — Redis, or Postgres if the
  deployment stays single-instance) vs a honeypot field vs a captcha.
- **Why code should wait:** each option writes a different storage layer; picking after
  implementing means rewriting it.
- **Blocks:** B3.11, and the unscheduled "rate limiting on checkout/payment" idea, which
  should be decided together so one canonical mechanism exists (R7).

### D2 — Notification provider
- **Decision:** Kavenegar vs National SMS vs SMTP, and whether transactional email is in
  scope at all.
- **Why code should wait:** F2.3 (password reset) cannot ship without a transport, and
  `[BE-07]`'s triggers assume SMS. The provider choice determines the whole service shape.
- **Blocks:** B2.1, F2.3, B2.5, and the notification half of B4.13. Strictly sequential.

### D3 — CSV product import semantics
- **Decision:** idempotency key (product `id` vs `name+category`), and overwrite vs skip
  vs upsert-only-empty-fields on conflict.
- **Why code should wait:** already flagged in the task text; the wrong key silently
  duplicates or clobbers catalogue rows.
- **Blocks:** B2.2a.

### D4 — Preorder fulfilment
- **Decision:** whether the store takes preorders at all; if yes, the order-level marker,
  the fulfilment rule and the customer notification.
- **Why code should wait:** B4.11 currently blocks `preorder` at stock-check and checkout
  **by an explicit earlier user decision**; reversing it needs an equally explicit one.
- **Blocks:** B4.13.

### D5 — Stock reservation TTL
- **Decision:** reserve-then-commit during checkout (with a TTL) vs the current
  decrement-at-order-creation.
- **Why code should wait:** it rewrites the same decrement/restore pair as B6.8 and
  touches money and stock invariants (R11). Doing both at once risks a half-migrated
  inventory model.
- **Blocks:** B4.9, and `[BE-05]`'s "reserve/commit stock on payment success".
- **Sequencing note:** must not start before B6.8 lands.

### D6 — Refund payout details (customer bank account)
- **Decision:** collect the customer's IBAN/Sheba at claim time (new PII to store,
  protect and audit) vs keep the current out-of-band process where only the admin's
  `bank_tracking_code` is recorded.
- **Why code should wait:** storing Iranian bank identifiers is a data-protection choice,
  not a UI detail.
- **Blocks:** the IBAN/Sheba panel of `[FE-06]`.

### D7 — Catalogue and CRM dimensions
- **Decision:** (a) does the catalogue need a third variant axis beyond size × color;
  (b) what defines the New/VIP/Wholesale customer tiers; (c) should guest
  recently-viewed be kept in localStorage and merged into the account list at sign-in.
- **Why code should wait:** all three are product policy, and (a) changes the
  `product_variants` unique key.
- **Blocks:** B4.8, AB-FE-06 (tier badge only), F3.4b.

### D8 — Install `@tanstack/react-table`
- **Decision:** adopt TanStack Table v8 for the reusable admin grid, or keep per-route
  bespoke tables.
- **Why code should wait:** R12 forbids drive-by dependency additions; this is a
  deliberate, reviewable choice.
- **Blocks:** F4.3 (and `[FE-02]`'s bulk-action bar).

### D9 — Low-stock threshold definition (documentation-only)
- **Decision:** retire `[BE-09]`'s hardcoded "< 5 units" in favour of the implemented
  per-product `low_stock_threshold`.
- **Why it matters:** otherwise the mismatch keeps reading as an open defect. Per Rule 0
  the spec is the user's document and this audit does not edit it.
- **Blocks:** nothing; it closes a false gap.

---

# 9. Newly Derived Tasks

## 9.1 Mapping table — requirements already covered (NO new task)

```
[BE-01] variants + composite key  → B4.3            (gaps only → AB-BE-01/AB-BE-02)
[BE-02] coupon engine + race      → B1.4 + B6.7     (gap only  → AB-BE-03)
[BE-03] refund processing         → B5.3 + B6.4     (RLS clause SUPERSEDED)
[BE-04] RBAC                      → B5.4
[BE-04] audit logging             → B5.1 + B5.1a    (tamper-resistance → B5.1b; UI → F5.5)
[BE-05] order lifecycle           → B6.1 / B6.3     (stock restore gap → B6.8; reserve → B4.9)
[BE-06] validateCoupon            → B1.4 + B6.7     (cap → AB-BE-03)
[BE-07] SMS gateway               → B2.1
[BE-08] exportOrders              → B2.2            (UI entry point → AB-FE-02)
[BE-09] getDashboardKPIs          → B5.2 + F2.6
[FE-00] design system             → F4.1 + DESIGN_SYSTEM.md
[FE-01] admin layout              → F4.2 + F5.1     (deferred topbar → AB-FE-01)
[FE-02] AdminDataTable            → F4.3            (export trigger → AB-FE-02)
[FE-03] KPI dashboard             → F2.6
[FE-04] product catalog mgmt      → F3.6            (editor → AB-FE-03; gallery → AB-FE-04;
                                                     pagination → AB-FE-05)
[FE-05] order drawer + invoice    → F4.4
[FE-06] refund center             → F2.4            (IBAN panel → decision D6)
[FE-07] coupons manager           → F4.5
[FE-08] role management           → F5.6            (profile/LTV/tiers → AB-FE-06)
```

**Explicit duplicates inside the existing task files** (see Drift 2): the B2-section
**B6.1** ("Order state machine"), the follow-up **B6.3** ("Order lifecycle per spec
[BE-05]") and the follow-up **B6.1** ("Seed jobs run the additive DDL") are three IDs
covering two features, with one ID reused. `B6.3 → maps to B6.1 (state machine)`.

## 9.2 New tasks — backend

### AB-BE-01 — `inventory_logs` stock ledger
- **Layer:** Backend · **Source:** proposed, from `[BE-01]` · **Status:** TODO · **Priority:** P2
- **Scope:** Idempotent DDL for `inventory_logs (id, variant_id, change_amount, reason
  ENUM('purchase','restock','return','manual_adjustment'), created_by, created_at)` in
  `app/db.py`. One canonical writer in a new `app/services/inventory_log.py` (R7),
  called from `app/services/checkout.py` (decrement → `purchase`),
  `app/services/order_lifecycle.py::restore_stock` (→ `return`) and the variant PATCH in
  `app/routers/products.py` (→ `manual_adjustment`). Read endpoint
  `GET /admin/inventory/logs` behind the existing `inventory`/`catalog` capability, with
  `services/pagination.py` envelope.
- **Acceptance criteria:** every stock mutation writes exactly one ledger row in the same
  transaction; a cancelled order's rows net to zero against its checkout rows; the
  endpoint returns the envelope and 403s for roles without the capability; new test in
  `backend/tests/` asserting checkout+cancel nets to zero (R11).
- **Backend dependencies:** **B6.8** — the ledger is keyed on `variant_id`, which order
  items do not yet carry.
- **Frontend dependencies:** none required; a viewer can follow later.
- **Security implications:** `created_by` must come from the authenticated staff user,
  never the request body. Append-only, same argument as B5.1b.
- **Blocks:** nothing.

### AB-BE-02 — Variant `sku` uniqueness, `price_override`, `color_hex`
- **Layer:** Backend · **Source:** proposed, from `[BE-01]` · **Status:** TODO · **Priority:** P2
- **Scope:** Additive columns `price_override NUMERIC NULL` and `color_hex TEXT NULL` on
  `product_variants`; a partial unique index on `sku` where not null. `price_override`
  honoured in `app/services/pricing.py` so the **backend stays the authoritative price**
  (R11) — the frontend must never compute it. `color_hex` exposed through the variant
  read/write schemas in `app/schemas.py`.
- **Acceptance criteria:** duplicate non-null SKUs are rejected with a clean 409, not a
  500; a variant with `price_override` prices at that value through `POST /stock/check`,
  `POST /checkout` and the cart quote, with a test covering the override path; existing
  rows with NULL `sku`/`price_override`/`color_hex` behave exactly as today.
- **Backend dependencies:** none.
- **Frontend dependencies:** AB-FE-03 consumes `color_hex` for the swatch picker.
- **Security implications:** price injection — `price_override` is read from the DB only,
  never accepted from the checkout body.
- **Blocks:** the colour-swatch half of AB-FE-03.

### AB-BE-03 — Coupon `max_discount_cap`
- **Layer:** Backend · **Source:** proposed, from `[BE-02]`/`[BE-06]` · **Status:** TODO · **Priority:** P1
- **Scope:** Additive nullable `max_discount_cap INTEGER` on `coupons`;
  `app/services/pricing.py` clamps the computed percentage discount to it;
  `POST /coupons/validate` returns the clamped amount; `app/routers/coupons.py` CRUD and
  the `/admin/coupons` UI (F4.5) expose the field.
- **Acceptance criteria:** a `percent_off` coupon with a cap never discounts more than the
  cap at validate **and** at redemption (the two must agree — the B6.7 lesson);
  `amount_off` coupons ignore it; NULL means uncapped, preserving today's behaviour for
  every seeded coupon; new test in `backend/tests/test_pricing_and_coupons.py` (R11).
- **Backend dependencies:** none. **Frontend dependencies:** one field in the F4.5 dialog.
- **Security implications:** revenue leakage, not access control.
- **Blocks:** nothing.

## 9.3 New tasks — frontend

### AB-FE-01 — Admin topbar completion
- **Layer:** Frontend · **Source:** proposed, from `[FE-01]`; completes F4.2 · **Status:** TODO · **Priority:** P2
- **Scope:** Breadcrumbs from the active route, staff avatar/initials dropdown with
  sign-out, sidebar collapse toggle with persisted state, `Cmd+K`/`Ctrl+K` command
  palette over the admin routes (the unused `src/components/ui/command.tsx`
  `CommandDialog` is the intended primitive), and a "preview storefront" link.
- **Acceptance criteria:** the palette lists only routes the current role may reach
  (reuse `ROLE_TAB_KEYS`, never a second source of truth — R7/R9); works at 375px and in
  the mobile Sheet; keyboard-navigable; all copy Persian.
- **Dependencies:** none. **Security:** the palette must not leak the existence of routes
  a role cannot open. **Blocks:** nothing.

### AB-FE-02 — Export controls for `/admin/export/*`
- **Layer:** Frontend · **Source:** proposed, from `[FE-02]`/`[BE-08]`; backend DONE as B2.2 · **Status:** TODO · **Priority:** P1
- **Scope:** A date-range + status export control on `/admin/orders` and an export button
  on `/admin/products`, both for CSV and XLSX. **Deliberately not blocked behind F4.3** —
  `backend-tasks.md` currently routes these buttons through the data grid's toolbar,
  which is why a finished backend feature has shipped nowhere (Drift 5).
- **Acceptance criteria:** the download carries the bearer token, so it goes through
  `src/lib/api.ts` as a blob fetch, **not** a bare `<a href>` (R7 — no direct `fetch` and
  no unauthenticated link); the filename from the RFC-6266 header is honoured; the
  control is hidden **and** the route 403s for roles without the `orders` capability;
  loading and error states; Persian labels.
- **Dependencies:** none (B2.2 shipped). **Security:** exports contain full customer
  shipping details and payment references — the guard is the point, and hiding the button
  is never the guard (R9). **Blocks:** nothing.

### AB-FE-03 — Two-column product editor with RHF/Zod and colour swatch picker
- **Layer:** Frontend · **Source:** proposed, from `[FE-04]` · **Status:** TODO · **Priority:** P2
- **Scope:** Restructure `admin.products.tsx`'s editor into the spec's two-column layout
  (wide: title, category, description; narrow: pricing, visibility switch, badges);
  migrate the hand-rolled state to React Hook Form + Zod; add the visual colour swatch
  picker to the variant row generator.
- **Acceptance criteria:** validation errors are per-field and Persian; the Zod schema
  mirrors the backend's `app/schemas.py` constraints without inventing new ones (R8); no
  change to the request/response shape; RTL layout holds at 768px and above, stacking below.
- **Dependencies:** **AB-BE-02** for `color_hex`. **Blocks:** nothing.

### AB-FE-04 — Image gallery manager
- **Layer:** Frontend · **Source:** proposed, from `[FE-04]` · **Status:** TODO · **Priority:** P2
- **Scope:** Upgrade `src/components/admin/ProductImageManager.tsx` with a drag-and-drop
  upload zone, per-file progress, reorderable preview cards, a primary-image star toggle
  and hover delete.
- **Acceptance criteria:** ordering and the primary flag persist through the existing
  product update contract; uploads keep going through `POST /storage/upload-url` to MinIO
  — **not** a direct bucket SDK (the spec's Supabase wording is STALE); the existing MIME
  check at `ProductImageManager.tsx:48` is kept, not weakened (R13).
- **Dependencies:** none. **Blocks:** nothing.

### AB-FE-05 — `/admin/products` server pagination
- **Layer:** Frontend · **Source:** proposed, from `[FE-04]`; completes F2.5 · **Status:** TODO · **Priority:** P1
- **Scope:** Move `admin.products.tsx` off the full-catalogue `useCatalog()` read onto the
  paginated `GET /products` envelope with the shared `Pager`, matching the F2.5 pattern
  used by `admin.orders.tsx`.
- **Acceptance criteria:** URL-driven `?page=`; search and filters survive paging; the
  admin list still shows inactive products (`include_inactive=true`); every admin mutation
  invalidates the right query key; empty/loading/error states.
- **Dependencies:** none — the backend envelope shipped with F2.5. **Blocks:** nothing.

### AB-FE-06 — Customer 360° profile
- **Layer:** Frontend (+ small backend aggregate) · **Source:** proposed, from `[FE-08]` remainder · **Status:** TODO · **Priority:** P3
- **Scope:** Per-customer drawer with avatar/initials, tier badge, LTV metric, average
  days between purchases, and tabs for Order History / Saved Addresses / Wishlist.
- **Acceptance criteria:** LTV and the purchase interval are computed **server-side** and
  exclude cancelled orders, consistent with `GET /admin/kpis` (R11 — the frontend never
  computes money); the tabs reuse existing endpoints rather than adding parallel ones (R7);
  403 for roles without the `users` capability, on direct URL entry too.
- **Dependencies:** a new aggregate field or endpoint alongside `app/routers/admin.py`;
  **decision D7(b)** for the tier thresholds — **the tier badge alone is blocked, the rest
  is not**. **Blocks:** nothing.

---

# 10. The P0 in full — B6.8

Recorded separately because it is the only correctness defect this audit found in
shipped code, and because the surrounding code reads as if it were already fixed.

**Claim in the repo.** `backend/app/services/order_lifecycle.py` lines 5-8 and 58-63
state that cancellation restores stock "variants first, then the product aggregate —
mirroring checkout's decrement order".

**Reality.**
1. `backend/app/services/checkout.py:226-232` decrements `product_variants.stock` for
   every line that resolved to a variant (`line["variant_id"]`, set at `:122`).
2. `backend/app/services/checkout.py:180-198` inserts order items with exactly
   `(order_id, product_id, name, price, size, color, image, quantity)` — **no
   `variant_id`**.
3. `infra/initdb/02-public-schema.sql:107-118` defines `order_items` without a
   `variant_id` column, and **no additive DDL in `backend/app/db.py` adds one**
   (`grep -n "order_items" backend/app/db.py` → no match).
4. `backend/app/services/order_lifecycle.py:63-75` probes
   `information_schema.columns` for `order_items.variant_id` and sets
   `has_variant_col`. That probe is always **false**, so the variant restore branch at
   `:88-95` is unreachable dead code.

**Consequence.** Every cancellation restores `products.stock` but leaves
`product_variants.stock` decremented forever. The aggregate and the per-combination
totals drift apart permanently and silently. Each cancelled variant order destroys that
combination's inventory.

**Why it outranks everything else.** It corrupts data continuously in normal operation,
it cannot be detected from the UI, and it has no workaround short of manual SQL.

**Acceptance criteria.**
1. Idempotent `ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS variant_id UUID
   REFERENCES public.product_variants(id) ON DELETE SET NULL` in `app/db.py`'s startup
   DDL — and, per B6.1, reachable by the seed jobs, which call `startup_ddl()` themselves.
2. `app/services/checkout.py` persists `line["variant_id"]`.
3. `restore_stock` restores the variant row and the aggregate in one transaction; the
   `information_schema` probe may be dropped or kept purely as a legacy guard.
4. Legacy rows (`variant_id IS NULL`) keep aggregate-only behaviour — **no backfill
   guess**, since the original combination cannot be recovered from `size`/`color` text
   reliably.
5. Repeat-cancel stays a no-op (R10: "what if this runs twice?").
6. New test in `backend/tests/`: order a variant → cancel → both `products.stock` and
   `product_variants.stock` return to their pre-order values; cancelling twice does not
   inflate either (R11).

**Verification level:** the defect is established from the schema and the INSERT
statement, which is conclusive at the code level. It was **not** reproduced against a
running stack in this session. Recommended runtime proof before and after the fix:
place a variant order, cancel it, and watch `product_variants.stock` on a live stack.

---

# 11. Dependencies

## 11.1 Hard dependencies

```
B6.8      → (none)
AB-BE-01  → depends on B6.8            (the ledger is keyed on order_items.variant_id)
B4.9      → depends on B6.8 + D5       (rewrites the same decrement/restore pair)
AB-FE-03  → depends on AB-BE-02        (colour swatch needs color_hex)
F2.3      → depends on B2.1 → D2       (no reset without a mail transport)
B2.5      → depends on D2              (notification half)
B4.13     → depends on D4, and D2 for notifications
B2.2a     → depends on D3
B3.11     → depends on D1
F4.3      → depends on D8
B4.8      → depends on D7(a)
F3.4b     → depends on D7(c)
AB-FE-06  → tier badge depends on D7(b); the rest is unblocked
[FE-06] IBAN panel → depends on D6     (not yet a task)
```

## 11.2 Explicitly independent (safe to run in parallel)

```
Can run in parallel, no shared files or contracts:
  - F5.5     audit-log viewer          (new route + new api.ts method)
  - F5.6     role management UI        (admin.users.tsx + new api.ts method)
  - AB-FE-02 export controls           (admin.orders.tsx / admin.products.tsx + api.ts)
  - AB-FE-05 admin products pagination (admin.products.tsx)
  - B6.9     refund exception handler  (routers/orders.py)
  - AB-BE-03 coupon cap                (db.py + services/pricing.py + coupons CRUD)
  - B5.1b    audit REVOKE              (infra DDL only)

Caution — AB-FE-02 and AB-FE-05 both touch admin.products.tsx; sequence them or
split by file to keep diffs minimal (R12).

Must happen first, then the dependent work:
  B6.8 (order_items.variant_id)   → then AB-BE-01 (inventory_logs), then B4.9
  AB-BE-02 (color_hex)            → then AB-FE-03 (swatch picker)
  Decision D2 → B2.1 (transport)  → then F2.3 (password reset) → then B2.5 → then B4.13
  Decision D8                     → then F4.3 (AdminDataTable) → then the bulk-action bar
```

## 11.3 Nothing blocks the P0

B6.8 has no upstream dependency and blocks two P2 items. It should be first.

---

# 12. Prioritization — P0 / P1 / P2 / P3

Priorities follow the definitions supplied with the request: P0 = correctness /
security / financial / inventory / data corruption; P1 = core product functionality;
P2 = quality / scalability; P3 = nice-to-have. Document order carries no weight.

## P0 — Blocking / correctness (1)

| ID | Title | Layer | Status | Why it matters |
|----|-------|-------|--------|----------------|
| B6.8 | Per-variant stock restoration on cancellation | Backend + DB | TODO | Inventory corruption on every cancellation of a variant order; silent and unbounded. See §10 |

## P1 — Core product (8)

| ID | Title | Layer | Source | Status | Why it matters | Depends on |
|----|-------|-------|--------|--------|----------------|------------|
| B6.9 | Narrow the refund exception handler | Backend | existing | TODO | A DB failure during a money operation is reported to the customer as a duplicate claim and never logged as an error | — |
| AB-BE-03 | Coupon `max_discount_cap` | Backend | new, `[BE-02]` | TODO | Percentage coupons discount without a ceiling — direct revenue leakage | — |
| F5.5 | Audit-log viewer | Frontend | existing | TODO | An audit trail nobody can read is not an audit trail; `[BE-04]`'s goal is unmet on the reading side | — |
| F5.6 | Role management UI | Frontend | existing | TODO | Staff role changes currently require a raw API call; `PUT /admin/users/{id}/roles` is shipped and audited | — |
| AB-FE-02 | Export controls for `/admin/export/*` | Frontend | new, `[FE-02]`/`[BE-08]` | TODO | A complete, guarded backend export feature is unreachable from the product | — |
| AB-FE-05 | `/admin/products` server pagination | Frontend | new, `[FE-04]` | TODO | The only admin list still loading the whole table; F2.5 covered every other one | — |
| B3.11 | Contact-form spam guard | Backend | existing | BLOCKED | An unauthenticated unbounded INSERT; a public-deploy blocker | D1 |
| F2.3 | Forgot password | Full-stack | existing | BLOCKED | Account recovery is a baseline auth flow and the backend endpoint does not exist | D2 → B2.1 |

## P2 — Quality / scalability (10)

| ID | Title | Layer | Source | Status | Depends on |
|----|-------|-------|--------|--------|------------|
| B5.1b | Audit-log tamper-resistance (`REVOKE`) | Infra/DB | existing | TODO | — |
| AB-BE-01 | `inventory_logs` stock ledger | Backend | new, `[BE-01]` | TODO | B6.8 |
| AB-BE-02 | Variant `sku` unique, `price_override`, `color_hex` | Backend | new, `[BE-01]` | TODO | — |
| F5.8 | `/shop` duplicate catalog fetch | Frontend | existing | TODO | — |
| F5.7 | Split the admin chart bundle | Frontend | existing | PARTIAL/mis-stated | re-measure first |
| F4.3 | Reusable admin data grid | Frontend | existing | BLOCKED | D8 |
| AB-FE-01 | Admin topbar completion | Frontend | new, `[FE-01]` | TODO | — |
| AB-FE-03 | Two-column product editor + RHF/Zod + swatch | Frontend | new, `[FE-04]` | TODO | AB-BE-02 |
| AB-FE-04 | Image gallery manager | Frontend | new, `[FE-04]` | TODO | — |
| F3.5b | Cart re-check on window focus | Frontend | existing | TODO | — |
| B2.5 | Webhooks + background jobs | Backend | existing | BLOCKED | D2 |

## P3 — Future / nice-to-have (5)

| ID | Title | Layer | Source | Status | Depends on |
|----|-------|-------|--------|--------|------------|
| B2.3 | PDF invoices | Backend | existing | TODO | — (F4.4's print invoice covers the practical need) |
| B4.8 | Product model dimension | Backend | existing | BLOCKED | D7(a) |
| F3.4b | Guest recently-viewed | Frontend | existing | BLOCKED | D7(c) |
| AB-FE-06 | Customer 360° profile | Full-stack | new, `[FE-08]` | TODO (tier badge blocked) | D7(b) for the badge only |
| F1.9 | Lovable preview tooling | Frontend | existing | TODO | app leaving Lovable |
| B2.2a | CSV product import | Backend | existing | BLOCKED | D3 |
| B4.13 | Preorder fulfilment flag | Backend | existing | BLOCKED | D4, D2 |

*(The P2 and P3 tables list 11 and 7 rows respectively because the blocked items appear
in their natural priority band; the headline counts in Final Numbers classify each item
once, by status, not twice.)*

---

# 13. Documentation Drift

1. **`B6.10` is marked `[ ]` but is implemented.** F2.5 added envelope pagination to
   `GET /products` (`app/routers/products.py:126-203`) and `GET /admin/orders`
   (`app/routers/admin.py:330-353`) through `app/services/pagination.py`. The backend
   checkbox was never ticked when its frontend twin shipped.
   → Should be `[x]` with a link to `audit/2026-09-22-f25-pagination-everywhere.md`.
2. **Duplicate task ID `B6.1`.** Used twice in `plan/backend-tasks.md`: once in the
   Milestone B2 section for the order state machine, once in the audit follow-ups for
   "Seed jobs run the additive DDL themselves". The state machine is *also* tracked as
   `B6.3`. Three IDs, two features, one collision. A downstream agent reading "B6.1"
   cannot tell which is meant.
3. **`B2.6` carries an open checkbox but is obsolete.** Its own body reads "nothing to
   build in Python… superseded by B1.9". It inflates the open count.
   → Per the standing rule against deleting tasks, strike it through with the reason.
4. **`order_lifecycle.py` documents behaviour that cannot happen.** Its module docstring
   (lines 5-8) and `restore_stock` docstring (lines 58-63) describe per-variant
   restoration as shipped. It is unreachable (§10). The comment should not read as
   shipped behaviour while the column is missing — this is how the gap stayed invisible.
5. **`B2.2`'s note misroutes its own follow-up.** It states the export buttons "should"
   live in F4.3's toolbar, which parks a finished P1-value backend feature behind an
   undecided dependency install (D8). AB-FE-02 unblocks it independently.
6. **`F5.7` names lodash as a direct dependency.** It is **not** in
   `vogue-vintage-vibes/package.json`; only `recharts ^2.15.4` (line 61) is. The quoted
   ~164 kB is transitive, so the stated fix does not match the actual bundle.
7. **`[BE-01]`, `[BE-03]`, `[BE-04]` RLS clauses — `SUPERSEDED`.** They specify
   `has_role(auth.uid(),'admin')` row-level security and `auth.users` foreign keys. This
   repo enforces authorization in `app/auth.py` + `app/services/roles.py` against
   `public.users`; there is no `auth` schema and no RLS. Rule 0.2: the live repo wins.
   Record, do not implement.
8. **`[FE-04]` "direct Supabase storage bucket upload" — `STALE`.** Uploads go through
   `POST /storage/upload-url` to MinIO (`app/routers/storage.py`, F1.1c). AB-FE-04 must
   use the existing path.
9. **`[BE-05]`/`[BE-08]`/`[BE-09]` "RPC" and `[FE-05]`/`[FE-06]` "TanStack server
   function" wording — `STALE`.** All frontend HTTP goes through `src/lib/api.ts` (R7);
   there are no Postgres RPCs and no `createServerFn`. The *requirements* inside those
   blocks are `CURRENT` and are mapped in §9.1 — only the mechanism wording is stale.
10. **`[FE-05]`'s stepper labels — `SUPERSEDED`, deliberately.** The spec's Placed ➔ Paid
    ➔ Processing ➔ Shipped was adapted to the frozen Rule-4 statuses
    (`pending → processing → shipped → delivered`) in F4.4. Correct call, already
    recorded in that task's audit. Flagged here so a future agent does not reopen it as a
    defect or "fix" it back into a Rule-4 violation.
11. **`[BE-09]`'s "< 5 units" low-stock rule — `NEEDS PRODUCT DECISION` (D9).** The repo
    uses a per-product `low_stock_threshold` (B4.1), which is better. Retiring the
    hardcoded 5 closes a false gap. The spec is the user's document and was not edited.
12. **The two ADMIN files are specifications, not tracked task lists.** Neither has
    checkboxes nor audit links, so the `AGENTS.md` tick-and-link workflow cannot apply to
    them, and counting their headings as tasks inflates the backlog. Either give them a
    mapping table — §9.1 above is usable verbatim — or relabel them as `design/` specs.
13. **`B1.3`'s title still says "Supabase JWT auth".** The implementation is the repo's
    own HS256 JWT (`app/security.py`), replaced by B1.9. The title is a leftover; the
    task is genuinely DONE.
14. **Three shipped backend features have no task tracking their missing UI.** B5.1's
    viewer became F5.5 and B5.4's role UI became F5.6 — but B2.2's export UI had no task
    at all until this audit (→ AB-FE-02). Worth a convention: a backend task that ships a
    staff-facing endpoint should open its frontend checkbox in the same session.

---

# 14. Recommended Implementation Order

Ordered by dependency and priority only.

```text
Phase 1 — P0 correctness
  1. B6.8       order_items.variant_id + checkout write + restore + test

Phase 2 — P1 backend  (2-3 parallel; 4 gated on D1)
  2. B6.9       narrow the refund exception handler
  3. AB-BE-03   coupon max_discount_cap
  4. B3.11      contact spam guard                    [Depends on: D1]

Phase 3 — P1 frontend  (all four parallelizable; may run alongside Phase 2)
  5. F5.5       audit-log viewer
  6. F5.6       role management UI
  7. AB-FE-02   export controls
  8. AB-FE-05   /admin/products pagination
                (7 and 8 both touch admin.products.tsx — sequence or split by file)

Phase 4 — P2 quality / scalability
  9. B5.1b      audit-log REVOKE + clean-environment proof (R14)
 10. AB-BE-01   inventory_logs                        [Depends on: B6.8]
 11. AB-BE-02   variant sku / price_override / color_hex
 12. F5.8       /shop duplicate catalog fetch
 13. F5.7       admin chart bundle split (re-measure first — see Drift 6)
 14. F4.3       AdminDataTable                        [Depends on: D8]
 15. AB-FE-01   admin topbar completion
 16. AB-FE-03   product editor                        [Depends on: AB-BE-02]
 17. AB-FE-04   image gallery manager
 18. F3.5b      cart re-check on focus

Phase 5 — P3 / decision-gated
 19. B2.1 → F2.3 → B2.5 → B4.13                       [Depends on: D2, strictly serial]
 20. B2.2a                                            [Depends on: D3]
 21. B4.9                                             [Depends on: D5, and B6.8]
 22. B2.3, B4.8, F3.4b, AB-FE-06, F1.9
```

**Rationale for the shape.** B6.8 is first because it is the only continuous data
corruption and because two later tasks (AB-BE-01, B4.9) build on the column it adds.
Phases 2 and 3 are deliberately concurrent: the P1 backend fixes and the P1 frontend
gaps share no files and no contracts. The decision-gated chain is last not because it is
unimportant — password reset is a baseline flow — but because no line of it can be
written correctly before D2 is answered.

---

# 15. Final Numbers / Statistics

```text
Existing tracked tasks:                                    135
  plan/backend-tasks.md:                                    61
  plan/frontend-tasks.md:                                   74

Actually complete (DONE):                                  118
Partial:                                                     4
Still required (TODO):                                      11
Blocked on a product/architecture decision:                  7
Obsolete:                                                    1
Duplicate:                                                   2
Unclear:                                                     0

Product decisions required:                                  9  (D1–D9; D9 is doc-only)
New tasks derived from ADMIN-BACKEND_TASKS.md:               3  (AB-BE-01..03)
New tasks derived from ADMIN-FRONTEND_TASKS.md:              6  (AB-FE-01..06)

Total actionable backlog:                                   24
  immediately actionable:                                   17
  decision-gated:                                            7
  by priority — P0 / P1 / P2 / P3:                 1 / 8 / 10 / 5

ADMIN spec blocks mapped to existing implementations:       13  (no duplicate task created)
ADMIN spec blocks needing new tasks:                         4  ([BE-01],[BE-02],[FE-01],[FE-04],[FE-08] partials)
Documentation drift items:                                  14
```

**Headline:** the store and admin panel are far more complete than the open checkboxes
suggest — 118 of 135 tracked items are genuinely done, and two of the remaining `[ ]`
items are already implemented. The real remaining work is **24 items**, of which **one
is a P0 inventory-corruption defect** and **four of the eight P1 items are frontend
entry points for backend features that already shipped**.

---

## Files changed

- `plan/audit/2026-09-22-full-backlog-audit.md` — this file (new).
- `plan/session-log.md` — session section appended, per `AGENTS.md` step 3.

**Deliberately untouched**, as instructed by the user and as required by the audit-only
scope:

- All production code (`backend/app/**`, `vogue-vintage-vibes/src/**`, `infra/**`) — no
  edit of any kind.
- `plan/backend-tasks.md` and `plan/frontend-tasks.md` — **no checkbox was ticked**,
  including `B6.10`, which this audit finds already implemented, and `B2.6`, which it
  finds obsolete. Both are recorded in Documentation Drift for the user or the next agent
  to action deliberately.
- `plan/ADMIN-BACKEND_TASKS.md`, `plan/ADMIN-FRONTEND_TASKS.md`,
  `design/SANDE_FULL_DEV_SPEC.md` — user documents (Rule 0).
- `AGENTS.md`, `plan/RULES.md` — explicitly out of scope.
- `plan/README.md` — still accurate; it indexes the folder, not individual audit files.
- `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
  `FEATURES.md`, `DESIGN_SYSTEM.md`, `plan/feature-roadmap.md` — no endpoint, setup step,
  script, stack, feature or design token changed, so `AGENTS.md` steps 4–6 do not apply.

## How to verify

```bash
# the report exists and is complete
wc -l plan/audit/2026-09-22-full-backlog-audit.md
grep -c "^# [0-9]" plan/audit/2026-09-22-full-backlog-audit.md   # 15 numbered sections

# nothing outside the two documentation files was touched
git show --stat HEAD

# spot-check the P0 claim (the single most important finding)
grep -n "variant_id" backend/app/services/checkout.py       # only the in-memory line dict
grep -n "order_items" backend/app/db.py                     # no match → no additive DDL
sed -n '107,118p' infra/initdb/02-public-schema.sql          # order_items has no variant_id

# spot-check the two drift claims
grep -n "page, page_size" backend/app/routers/products.py   # B6.10 is implemented
grep -n "audit" vogue-vintage-vibes/src/lib/api.ts          # no match → F5.5 is real
```

## What is NOT done / open

- **This audit did not execute anything** — no `pytest`, `ruff`, `api_smoke.py`,
  `bun run lint/build` or Docker run in this session. Every status is *inspected*, not
  *verified*, except where a prior audit file is cited by name (§3.4). Rules 13 and 14 do
  not apply to a markdown-only change, but the distinction matters for the agent
  consuming this file: **do not treat "implemented" here as "tested".**
- **The P0 was not reproduced at runtime.** B6.8 is established from the schema and the
  INSERT statement. Runtime proof — order a variant, cancel, watch
  `product_variants.stock` — should be part of the fix, not of this audit.
- **No checkbox was corrected**, although two are demonstrably wrong (`B6.10` implemented,
  `B2.6` obsolete) and one ID collides (`B6.1`). Correcting them is a documentation change
  the user or the next agent should make deliberately; this audit only reports.
- **The nine decisions D1–D9 are not made here.** Seven backlog items stay blocked until
  they are.
- **`[FE-06]`'s IBAN/Sheba panel has no task**, deliberately: it needs decision D6 first,
  and creating a task for PII storage before that decision would be premature.
