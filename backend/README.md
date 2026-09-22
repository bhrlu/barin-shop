# SÂNDÉ Backend (FastAPI)

The **sole backend** for the SÂNDÉ store: own JWT auth, product catalog,
cart/checkout, coupons, payments (Zarinpal), stock, MinIO object storage and the
admin API. The frontend (`vogue-vintage-vibes/`) talks only to this service — **no
Supabase**.

## Layout

```
backend/
├── pyproject.toml         # deps: fastapi, sqlalchemy, asyncpg, python-jose, minio …
├── .env.example           # DATABASE_URL, JWT_SECRET, MINIO_*, ZARINPAL_*, URLs
├── app/
│   ├── main.py            # FastAPI app + CORS + Zarinpal Status mapping
│   ├── config.py          # pydantic-settings
│   ├── db.py              # async engine + idempotent coupon & catalog DDL
│   ├── models.py          # SQLAlchemy models (mirrors the Postgres schema)
│   ├── security.py        # HS256 JWT + bcrypt password hashing
│   ├── auth.py            # CurrentUser / AdminUser / OptionalUser dependencies
│   ├── schemas.py         # pydantic request/response models
│   ├── seed_auth.py       # bootstrap admin + demo customer + demo staff (order_manager / support)
│   ├── seed_products.py   # 20-product catalog + browse tags (idempotent)
│   ├── seed_demo.py       # demo addresses/favorites/orders
│   ├── seed_coupons.py    # SANDE10 + WELCOME500
│   ├── seed_mock.py       # optional demo dataset: 8 customers, 31 backdated orders,
│                          # refund claims in all 4 states, reviews, inbox, variants
│   ├── services/          # coupons, checkout, payments, pricing, search, roles, variants
│   └── routers/           # health, auth, products, reviews, addresses, favorites,
│                          # orders, admin, storage, search, stock, coupons, checkout, payments
└── tests/                 # pytest units + tests/api_smoke.py (live end-to-end)
```

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then fill DATABASE_URL + JWT_SECRET
python -m app.seed_auth       # bootstrap admin + demo customer + demo staff
python -m app.seed_products   # 20 catalog products + tags
python -m app.seed_coupons    # starter coupons
python -m app.seed_mock       # optional: fills the admin screens with demo activity
uvicorn app.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs.

> `app.seed_mock` is **optional** and not part of the compose `db-init` chain — run
> it by hand when you want a populated dashboard (`docker compose exec backend
> python -m app.seed_mock`). It is idempotent and deterministic: a second run is a
> no-op, and every fresh database produces the same figures. Its customers sign in
> with `customer1234`.

> `DATABASE_URL` must use the **asyncpg** driver
> (`postgresql+asyncpg://…`) — bare `postgresql://` fails (`psycopg2` not installed).
> The compose stack in `infra/` is the easiest way to get a database + MinIO.

## Auth model

The service issues **its own HS256 JWTs** via `/auth/login` (bcrypt-hashed
passwords in `public.users`). Every user endpoint requires
`Authorization: Bearer <token>`; roles are resolved from `public.user_roles`
(DB is source of truth, token claim is the fallback). Admin routes return 403 for
callers without the route's capability. Staff authorization is capability-based
(B5.4): routes declare `require_staff("orders")`-style deps and
`app/services/roles.py::ROLE_CAPABILITIES` maps capabilities → staff roles
(`admin`/`super_admin` full; `order_manager` fulfillment/catalog/coupons;
`support` inbox/reviews/stats). `OptionalUser` resolves a caller when present but
stays anonymous otherwise (used to personalise search history).

## API summary

Public / customer:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | liveness (used by the compose healthcheck) |
| POST | `/auth/signup` · `/auth/login` | – | register / sign in → token |
| GET/PATCH | `/auth/me` | user | profile read / update |
| GET | `/products` | optional | catalog list — filters `category, tag, badge, availability, on_sale, size, color, min_price, max_price` + `sort`. `size`/`color` are **multi-value** (repeatable and/or comma-separated) |
| GET | `/products/compare?ids=` | – | side-by-side comparison |
| GET | `/products/{id}` | – | one product (with `avg_rating`, `review_count`) |
| GET | `/products/{id}/related` · `/recommendations` | – | discovery |
| GET | `/products/{id}/variants` | – | per size×color stock |
| GET/POST | `/products/{id}/reviews` | – / user | reviews + rating summary |
| DELETE | `/reviews/{id}` | user | delete own review |
| POST | `/products/{id}/view` · GET `/recently-viewed` | user | view tracking |
| GET | `/search?q=` · `/search/suggest` | optional | search (name, description, material, category, tags) + autocomplete |
| GET/DELETE | `/search/history` | user | recent searches |
| POST | `/stock/check` | – | pre-check cart lines (availability-gated, variant-aware) |
| POST | `/coupons/validate` | user | validate a code against a subtotal |
| POST | `/checkout` | user | create order (stock-locked, coupon applied) |
| GET | `/orders` · `/orders/{id}` | user | my orders / one order |
| POST | `/orders/{id}/cancel` · `/refunds` | user | cancel / refund request |
| PATCH | `/orders/{id}` | admin | status + payment status + shipment tracking code (`tracking_code`; empty string clears). Status changes pass the **state machine (B6.1)**: pending→processing→shipped→delivered, cancel from pending/processing, terminal delivered/cancelled — illegal moves get 409; cancellation restores stock |
| GET | `/orders/{id}/payment-session` | user | simulated gateway session |
| POST | `/orders/{id}/payment-complete` | user | simulated gateway callback |
| GET | `/payments/mine` | user | payment history |
| POST | `/payments/start` · `/payments/verify` | user | real Zarinpal session / verify |
| GET | `/payments/zarinpal/callback` | – | gateway return (redirects to the frontend; idempotent) |
| GET/POST/PATCH/DELETE | `/addresses` | user | address book (at most one `is_default`; `PATCH` edits and/or moves the default) |
| POST | `/contact` | – | store a contact-form message (guest-friendly) |
| GET/POST | `/favorites` · `/favorites/{id}` | user | wishlist |
| POST | `/storage/upload-url` · `/storage/sign` | admin / user | MinIO presign |

Admin:

| Method | Path | Purpose |
|---|---|---|
| POST/PATCH/DELETE | `/products` · `/products/{id}` | product CRUD (soft-delete if ordered) |
| POST/PATCH/DELETE | `/products/{id}/variants` · `/variants/{id}` | variant stock CRUD |
| GET/PATCH | `/admin/reviews` · `/reviews/{id}` | moderation + seller reply |
| GET | `/admin/inventory` · `/admin/inventory/low-stock` | stock health / alerts |
| GET | `/admin/stats` · `/users` · `/orders` · `/payments` · `/refunds` | dashboards (refunds carry the claimant's name/email) |

**Co-purchase recommendations (B2.4):** every multi-item order votes on each
product pair it contains (`public.co_purchases`, refreshed in the checkout
transaction and at startup). `GET /products/{id}/recommendations` blends
votes ×3 with the category/popularity heuristic; the payload shape is
unchanged. `GET /products/{id}/related` stays purely same-category.

**Pagination (F2.5):** `/products`, `/orders`, `/admin/orders`, `/admin/users`,
`/admin/payments`, `/admin/contact-messages` and `/admin/reviews` accept
`?page=&page_size=` (cap 100, default 20) and return
`{items, total, page, page_size, pages}`. **Without `?page=` they keep
returning bare arrays.** `/admin/audit-logs` uses `?limit=&offset=` instead
(append-only log).
| GET | `/admin/kpis?range=today\|7d\|30d\|all` | KPI aggregation: gross/net revenue, paid orders, AOV, pending refunds, low-stock, daily revenue series, status breakdown, deltas |
| GET | `/admin/audit-logs` | audit trail (B5.1): filters `action`, `entity_type`, `entity_id`, `admin_id`, `limit`/`offset` paging; written automatically on privileged mutations |
| PUT | `/admin/users/{id}/roles` | set a user's staff roles `super_admin`/`order_manager`/`support` (B5.4, audited) |
| PATCH | `/refunds/{id}` | resolve a refund request — settling (`refunded`) **requires** `bank_tracking_code` (Paya/Satna); every resolution records `resolved_by` + `resolved_at` |
| GET/DELETE | `/admin/contact-messages` | contact inbox (`?status=new`), delete a message |
| PATCH | `/admin/contact-messages/{id}` | mark a message `answered` (or reopen it as `new`) |
| POST/GET/PATCH | `/coupons` · `/coupons/{id}` · `/coupons/generate` | coupon CRUD — incl. `max_discount_cap`, the ceiling (in tomans) on a **percent-off** discount; `null` = uncapped, and `PATCH` with `0` clears it |
| DELETE | `/coupons/{id}` | remove a coupon (audited; past order discounts unaffected) |
| GET | `/admin/export/orders.{csv\|xlsx}?from=&to=&status=` | order ledger export (B2.2/BE-08): customer, address, item breakdown, subtotal/discount/shipping/total; `from` defaults 30 days back, invalid range → 422 |
| GET | `/admin/export/products.{csv\|xlsx}` | full catalog with stock/thresholds |
| GET | `/admin/export/report?from=&to=` | daily/monthly revenue (cancelled excluded) + top-10 best-sellers JSON |

Export notes (AB-FE-02): `from`/`to` are read as UTC wall-clock time (a supplied
offset is currently dropped — B2.2b) and `to` is exclusive, so the admin UI
sends local midnights as offset-less UTC ISO strings. CORS exposes
`Content-Disposition` so the browser can read the RFC-6266 filename on a
cross-origin download. UI: `/admin/orders` and `/admin/products`.

## Search model

`GET /search` matches `ILIKE %q%` across name, description, material, category
and the `tags` array, ranked **name > category > tag > description/material**;
the response carries `total` for pagination and signed-in queries are recorded in
`search_history`. `GET /search/suggest` mixes the caller's recent queries,
matching categories and tags, then product names. Tags are a browse vocabulary
(material, fit, season) supplied by `app/seed_products.py`, which backfills them
on rows that have none — so a catalog seeded before tags existed starts matching
tag queries without a reset.

## Stock model

`products.stock` is the aggregate; optional `product_variants` rows hold stock
per **size × color**. When a variant exists for a combination it is
**authoritative** (its own `active` flag can disable a single combination);
otherwise the product's aggregate stock applies. Checkout locks rows `FOR UPDATE`
and decrements with a guarded `UPDATE … WHERE stock >= qty` so nothing can
oversell. Shared by `POST /stock/check` and checkout via `app/services/variants.py`.

Each order line records the variant it drew from in `order_items.variant_id`, so
cancelling an order (`POST /orders/{id}/cancel` or an admin `PATCH` to
`cancelled`) restores the variant row **and** the product aggregate in the same
transaction (`app/services/order_lifecycle.py`). Lines with no variant row keep
`variant_id = NULL` and restore the aggregate only; a repeated cancellation
moves no stock.

### Availability gate

`products.availability` (`in_stock` / `coming_soon` / `preorder`) is a **hard
gate** checked before stock in both `POST /stock/check` and checkout: anything
other than `in_stock` is rejected with reason `not_available`, whatever the stock
says. Preorder is intentionally not orderable yet (the order schema has no
preorder fulfilment flag); enabling it means relaxing
`app/services/availability.py` and adding that flag — nothing else assumes it.

Every rejected line reports a `reason` from one closed set (`app/schemas.py`):
`not_found`, `inactive`, `not_available`, `size_invalid`, `insufficient_stock`.
`/stock/check` returns them directly; checkout returns them inside the
`stock_conflict` 409 payload, and the frontend keeps one copy of the Persian
copy for both (`src/lib/stock-issues.ts`).

## Payment sessions

`POST /payments/start` writes a pending `payments` row and keeps the gateway
**authority in its own `payments.authority` column** (`reference` starts as the
authority, so a pending row reads exactly as before, and becomes the `SND-…`
reference on success). `verify_and_finalize` looks the session up by authority and
is **idempotent**: a repeated gateway callback or a second `POST /payments/verify`
reports `already_paid` (HTTP 200 / a redirect to the same order page) instead of
failing to find the row. Rows written before the column existed are still found
through the `reference = authority` fallback.

## Address book

A customer has **at most one default address**: the first one created becomes the
default, an explicit `is_default` moves the flag, `PATCH /addresses/{id}` edits
fields and/or promotes, and deleting the default promotes the most recent
survivor. `GET /addresses` returns defaults first so the checkout pre-fill is
deterministic, and `POST /checkout` stores the shipping address (including the
optional `province`) in `orders.shipping_address`.

### Catalog facets

`size` and `color` accept repeated and/or comma-separated values
(`?size=M&size=L`, `?size=M,L` — both normalised by
`app/services/catalog_filters.py`). Values are OR within a facet and AND across
facets, resolved **per combination**: when both are given, at least one requested
size × colour pair must still be purchasable, so a pair the admin deactivated with
a variant row is not counted as offered.

## Catalog DDL

The coupon **and** catalog tables/columns are created idempotently on startup
(`app/db.py`), so a fresh database and an already-seeded one both converge. The
base schema comes from `infra/initdb/`; this service owns only the additive
columns (including `payments.authority` and `order_items.variant_id`) and the
`coupons` (incl. `coupons.max_discount_cap`), `product_variants`,
`product_reviews`, `search_history`,
`recently_viewed`, `contact_messages` tables.

## Tests

```bash
./.venv/bin/python -m pytest -q            # unit tests (no DB needed)
./.venv/bin/python -m ruff check app tests
./.venv/bin/python tests/api_smoke.py      # live end-to-end; needs a running API
```

`tests/api_smoke.py` logs in as the seeded customer + admin and exercises every
route, reporting any 5xx. It is **not** collected by pytest (it needs a live
server).

## Frontend integration

```ts
import { api } from "@/lib/api";           // single data layer
const products = await api.products({ sort: "rating", on_sale: true });
const order = await api.checkout({ lines, address, coupon_code });
```

The browser talks to this service directly at `VITE_API_URL`. Checkout is
server-priced; the cart only sends the applied coupon **code**, never an amount.
`app/services/coupons.py::compute_discount` is the single place a discount is
computed, so `POST /coupons/validate` and checkout always agree — including the
`max_discount_cap` ceiling, which applies to percent-off coupons only (a fixed
`amount_off` is already its own ceiling).
See `plan/frontend-tasks.md` Milestone F3 for the catalog UI still to be wired.
