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
│   ├── db.py              # async engine + idempotent coupon, catalog & profile DDL
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
│   ├── services/          # coupons, checkout, payments, pricing, search, roles, variants,
│                          # notifications (+ notification_providers: Kavenegar / SMTP),
│                          # inventory_log (stock ledger), profile (national-ID / birth-date /
│                          # measurement validation, F5.20), jobs (B2.5 background jobs)
│   ├── worker.py          # B2.5: `python -m app.worker` — runs services/jobs.py
│   └── routers/           # health, auth, profile (size-profile, F5.20), products, reviews, addresses,
│                          # favorites, orders, admin, storage, search, stock, coupons, checkout, payments,
│                          # notifications
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
| GET/PATCH | `/auth/me` | user | profile read / update — identity fields (first/last name, birth date, gender), `national_id`, verification timestamps, plus the legacy `full_name`/`phone`/`avatar_url`. PATCH: omitted = unchanged, explicit `null` = cleared (F5.20); `full_name` is derived from first/last when they are supplied |
| GET/PATCH | `/auth/me/size-profile` | user | the caller's optional fashion measurements — height/weight/chest/waist/hip (cm/kg, CHECK-bounded), preferred top/bottom/shoe sizes, fit preference; row is created on first PATCH; `national_id` and this endpoint's data are returned **only to their owner** (F5.20) |
| POST | `/auth/password/forgot` | – | `{email}` → **202** with the same message for every address (never reveals an account); emails a one-time link if the account exists (F2.3) |
| POST | `/auth/password/reset` | – | `{token, password}` → 200; 400 for an unknown / used / superseded / expired link |
| GET | `/products` | optional | catalog list — filters `category, tag, badge, availability, on_sale, size, color, min_price, max_price` + `sort`. `size`/`color` are **multi-value** (repeatable and/or comma-separated) |
| GET | `/products/facets` | – | `/shop` filter options — sizes, colours, tags and `price_min`/`price_max` of the **active** catalogue (F5.8) |
| GET | `/products/compare?ids=` | – | side-by-side comparison |
| GET | `/products/{id}` | – | one product (with `avg_rating`, `review_count`) |
| GET | `/products/{id}/related` · `/recommendations` | – | discovery |
| GET | `/products/{id}/variants` | – | per size×color stock, `sku`, `price_override`, `color_hex` (AB-BE-02) |
| GET/POST | `/products/{id}/reviews` | – / user | reviews + rating summary |
| DELETE | `/reviews/{id}` | user | delete own review |
| POST | `/products/{id}/view` · GET `/recently-viewed` | user | view tracking |
| GET | `/search?q=` · `/search/suggest` | optional | search (name, description, material, category, tags) + autocomplete |
| GET/DELETE | `/search/history` | user | recent searches |
| POST | `/stock/check` | – | pre-check cart lines (availability-gated, variant-aware); returns the server `subtotal` and `unit_prices` per line in request order (variant `price_override` included — F5.18) |
| POST | `/coupons/validate` | user | validate a code against a subtotal |
| POST | `/checkout` | user | create order (stock-locked, coupon applied) |
| GET | `/orders` · `/orders/{id}` | user | my orders / one order |
| POST | `/orders/{id}/cancel` · `/refunds` | user | cancel / refund request |
| PATCH | `/orders/{id}` | admin | status + payment status + shipment tracking code (`tracking_code`; empty string clears). Status changes pass the **state machine (B6.1)**: pending→processing→shipped→delivered, cancel from pending/processing, terminal delivered/cancelled — illegal moves get 409; cancellation restores stock **exactly once** — the status flip is a compare-and-set, so a customer cancel racing a staff cancel restores once and the loser gets 409 (PATCH) or the idempotent 200 (POST /cancel) (B6.19) |
| GET | `/orders/{id}/payment-session` | user | simulated gateway session |
| POST | `/orders/{id}/payment-complete` | user | simulated gateway callback |
| GET | `/payments/mine` | user | payment history |
| POST | `/payments/start` · `/payments/verify` | user | real Zarinpal session / verify |
| GET | `/payments/zarinpal/callback` | – | gateway return (redirects to the frontend; idempotent) |
| GET/POST/PATCH/DELETE | `/addresses` | user | address book (at most one `is_default`; `PATCH` edits and/or moves the default) |
| POST | `/contact` | – | store a contact-form message (guest-friendly). **Guarded (B3.11):** 5 attempts per IP per 10 min (accepted and rejected both count) → generic 429; a filled honeypot field `website` → generic 400, not stored |
| GET/POST | `/favorites` · `/favorites/{id}` | user | wishlist |
| GET | `/notifications?page=&page_size=&unread=` | user | own in-app notifications, newest first — **always** the `{items,total,page,page_size,pages}` envelope (default 20, cap 100); `unread=true` filters (B2.1) |
| GET | `/notifications/unread-count` | user | `{unread}` for the header bell |
| PATCH | `/notifications/{id}/read` | user | mark one read (idempotent: keeps the first `read_at`); someone else's id → 404 |
| POST | `/notifications/read-all` | user | mark all own unread → `{updated}` |
| POST | `/storage/upload-url` | `catalog` staff (admin, super_admin, order_manager — B6.17) | MinIO **POST policy** (B6.18): `{path, upload_url, fields, max_bytes}` — the policy pins the key, caps the object at 5 MB and requires `Content-Type: image/*`, so MinIO refuses an oversized or non-image upload; a non-image request `content_type` is a 422 |
| POST | `/storage/sign` | user | presigned GET URLs for `uploads/…` refs (anything else → `url: null`) |

Admin:

| Method | Path | Purpose |
|---|---|---|
| POST/PATCH/DELETE | `/products` · `/products/{id}` | product CRUD (soft-delete if ordered) |
| POST/PATCH/DELETE | `/products/{id}/variants` · `/variants/{id}` | variant CRUD: stock, `sku` (unique when set; duplicate → 409), `price_override` (> 0; PATCH `0` clears), `color_hex` (`#rrggbb`; PATCH `""` clears) |
| GET/PATCH | `/admin/reviews` · `/reviews/{id}` | moderation + seller reply |
| GET | `/admin/inventory` · `/admin/inventory/low-stock` | stock health / alerts |
| GET | `/admin/inventory/logs` | stock ledger (AB-BE-01), newest first, page envelope; filters `product_id`, `variant_id`, `order_id`, `reason` (`purchase`/`restock`/`return`/`manual_adjustment`); `catalog` staff only |
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

**Admin list filters (F4.3, all optional — omitted = the old answer):**
`/admin/orders` takes `status` (repeatable / comma-separated; unknown → 422),
`payment_status`, `q` (order number, receiver name, phone, customer email or
tracking code; LIKE wildcards are literal) and `sort=new|old|total_desc|total_asc`;
`/admin/users` takes `q` (email, name, phone), `role=staff|customer` and
`sort=new|spent|orders`. The admin data table (`AdminDataTable`) drives them.
| GET | `/admin/kpis?range=today\|7d\|30d\|all` | KPI aggregation: gross/net revenue, paid orders, AOV, pending refunds, low-stock, daily revenue series, status breakdown, deltas |
| GET | `/admin/audit-logs` | audit trail (B5.1): filters `action`, `entity_type`, `entity_id`, `admin_id` (a UUID — malformed → 422, B5.1c), `limit`/`offset` paging; written automatically on privileged mutations. **Append-only at the DB level (B5.1b):** triggers refuse UPDATE/DELETE/TRUNCATE; deleting a user only nulls `admin_id` |
| PUT | `/admin/users/{id}/roles` | set a user's staff roles `super_admin`/`order_manager`/`support` (B5.4, audited). **409** if the caller would remove their own role-management access or leave no account holding it (B5.4a; serialized by an advisory lock) |
| GET/PATCH | `/admin/settings/notifications` | SMS/email switches (B2.1, `settings` capability = admin/super_admin). `PATCH {sms_enabled?, email_enabled?}` (strict booleans, at least one → else 400; audited). Response adds per channel `*_provider`, `*_configured` (credentials present) and `*_active` (switch **and** configured); `internal_enabled` is always `true` |
| PATCH | `/refunds/{id}` | resolve a refund request — settling (`refunded`) **requires** `bank_tracking_code` (Paya/Satna); every resolution records `resolved_by` + `resolved_at` |
| GET/DELETE | `/admin/contact-messages` | contact inbox (`?status=new`), delete a message |
| PATCH | `/admin/contact-messages/{id}` | mark a message `answered` (or reopen it as `new`) |
| POST/GET/PATCH | `/coupons` · `/coupons/{id}` · `/coupons/generate` | coupon CRUD — incl. `max_discount_cap`, the ceiling (in tomans) on a **percent-off** discount; `null` = uncapped. `PATCH`: omitted/`null` = unchanged; `max_discount_cap: 0` / `max_uses: 0` clear the cap, `expires_at: ""` clears the expiry; sending `percent_off` clears `amount_off` and vice versa (both → 422) — F5.16. `POST` needs exactly one of `percent_off` / `amount_off` (both or neither → 422, B6.15) |
| DELETE | `/coupons/{id}` | remove a coupon (audited; past order discounts unaffected) |
| GET | `/admin/export/orders.{csv\|xlsx}?from=&to=&status=` | order ledger export (B2.2/BE-08): customer, address, item breakdown, subtotal/discount/shipping/total; `from` defaults 30 days back, `to` exclusive; ISO bounds — an explicit offset is converted to UTC, a naive value is UTC (B2.2b); invalid / inverted range → Persian 422. CSV bodies start with a UTF-8 BOM so Excel reads Persian directly (B2.2b) |
| GET | `/admin/export/products.{csv\|xlsx}` | full catalog with stock/thresholds |
| GET | `/admin/export/report?from=&to=` | daily/monthly revenue (cancelled excluded) + top-10 best-sellers JSON |

Export notes (AB-FE-02): `from`/`to` are read as UTC wall-clock time (a supplied
offset is currently dropped — B2.2b) and `to` is exclusive, so the admin UI
sends local midnights as offset-less UTC ISO strings. CORS exposes
`Content-Disposition` so the browser can read the RFC-6266 filename on a
cross-origin download. UI: `/admin/orders` and `/admin/products`.

## Background jobs (B2.5)

`python -m app.worker` (compose service `worker`) runs `app/services/jobs.py` every
`JOBS_INTERVAL_SECONDS` (60); `--once` runs one pass and exits. Each job runs in one
transaction behind a Postgres advisory lock (`job:<name>`), so extra workers or a
manual `--once` next to the service are safe — a worker that finds the lock taken
skips that tick. Jobs:

- **`sweep_deliveries`** — the notification outbox: a `pending` delivery older than
  `NOTIFICATION_PENDING_STALE_SECONDS` (120; its after-commit send was lost to a crash
  or restart) is dispatched; a `failed` one is retried after
  attempts × `NOTIFICATION_RETRY_BACKOFF_SECONDS` (120) until
  `NOTIFICATION_RETRY_MAX_ATTEMPTS` (5). Rows are locked `SKIP LOCKED`, `sent` /
  `skipped` rows are never touched; delivery is at-least-once only across a crash in
  the middle of a send.
- **`remind_unpaid_orders`** — one `payment_reminder` notification («یادآوری پرداخت
  سفارش», in-app + SMS/email when switched on) for each order still `pending` +
  `unpaid` `PAYMENT_REMINDER_AFTER_MINUTES` (60) after checkout and not older than
  `PAYMENT_REMINDER_MAX_AGE_HOURS` (72), through `notify_order_event`; the event key
  `order:<id>:payment_reminder` makes repeats no-ops.

No outbound webhooks yet: which systems would receive order events, and how they are
signed, is an open product decision (B2.5a).

## Notifications (B2.1)

`app/services/notifications.py` is the **only** place notifications are created.
Business code calls `notify_order_event(session, order_id, "created"|"paid"|"shipped"|"cancelled")`
or `notify_refund_event(session, refund_id, "approved"|"settled")` at the
lifecycle point itself: `services/checkout.create_order`, `services/payments.verify_and_finalize`,
the simulator `POST /orders/{id}/payment-complete`, a staff `PATCH /orders/{id}`
to `shipped` or `payment_status=paid`, `services/order_lifecycle.cancel_order_tx`
(both cancel paths), and `PATCH /refunds/{id}` to `approved` / `refunded`. A
rejected refund notifies nobody (D2 scope).

- **Same transaction.** The `notifications` row is inserted on the caller's
  session, so it commits or rolls back with the order/payment/refund.
- **One dedup mechanism.** `UNIQUE (user_id, event_key)` with keys like
  `order:<id>:paid` / `refund:<id>:settled`; a repeated transition inserts nothing
  and therefore sends nothing.
- **External channels are an outbox.** For a *new* notification, each channel the
  admin switched on (`notification_settings`) gets a `notification_deliveries`
  row: `pending` when the provider is configured and a recipient exists (profile
  phone → order shipping phone for SMS; account email), else `skipped` with
  `provider_not_configured` / `no_recipient`. Pending rows are sent in the
  background **after the commit**; a provider failure is stored (`failed` +
  `last_error`) and never touches the business transaction. Re-dispatching is
  safe — only `pending`/`failed` rows are picked, under a row lock. The B2.5
  worker's sweeper sends rows a crash left `pending` and retries `failed` ones
  (see *Background jobs* below).
- **Providers** (`services/notification_providers.py`): `KavenegarSmsProvider`
  (`KAVENEGAR_API_KEY`, optional `KAVENEGAR_SENDER`) and `SmtpEmailProvider`
  (`SMTP_HOST`, `SMTP_PORT`=587, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`,
  `SMTP_STARTTLS`=true, `SMTP_SSL`=false). Environment only — never the DB. Empty
  = unconfigured, a valid state. **Neither has been run against the real service
  yet** (no credentials exist); they are tested with stub transports only.
- The in-app inbox has no switch; SMS and email default to **off**.
- **Secret-bearing email** (the F2.3 reset link) uses
  `queue_private_email()`: same switch + configured rule, sent after COMMIT, but
  **no** outbox row (the body would put the secret in the DB) — sent once, failures
  logged without the body.

## Password reset (F2.3)

`services/password_reset.py`. `password_reset_tokens` keeps only the SHA-256 of
`secrets.token_urlsafe(32)`; a link lasts `PASSWORD_RESET_TTL_MINUTES` (30), works
once, and a newer request spends older links; at most
`PASSWORD_RESET_MAX_PER_HOUR` (3) links per account per hour — over the cap, and
for unknown addresses, `/auth/password/forgot` answers exactly the same. The link
is `${FRONTEND_URL}/reset-password?token=…`. With SMTP unconfigured nothing is
sent (no dev shortcut prints the link); to see the email locally, point `SMTP_*`
at a mail catcher and switch email on in `/admin/settings`. A reset stamps
`users.password_changed_at`; `app/auth.py` then rejects every token issued before
it (401; anonymous on optional-auth endpoints) — B6.14.

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

**Stock ledger (AB-BE-01).** `public.inventory_logs` records every stock movement in
the transaction that makes it, through `services/inventory_log.log_stock_change`:
checkout → `purchase` (−qty per line), cancellation → `return` (+qty, so an order's
rows net to zero), a new product / variant → `restock` (opening stock), a staff stock
edit → `manual_adjustment` (the delta; the row is locked first so the delta is exact).
`variant_id` NULL = the product's aggregate. Append-only (triggers refuse UPDATE /
DELETE / TRUNCATE) and without foreign keys, so a row keeps the ids it was written
with after those rows are deleted. Seeded stock predates the ledger.

**Variant price (AB-BE-02).** A variant may carry `price_override` (NULL = the
product's price). `variants.variant_price()` resolves a line's unit price from the
locked database rows, never from the request, for both the stock-check quote and
the order (`order_items.price`), so coupon discounts and shipping use the overridden
subtotal. The storefront shows these server prices (F5.18): the product page uses the
selected variant's override, and the cart/checkout take line prices and the subtotal
from the `POST /stock/check` quote.

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
`recently_viewed`, `contact_messages`, `contact_attempts`, `notifications`,
`notification_deliveries`, `notification_settings` (single row),
`user_size_profiles` (F5.20 one-to-one size profile) tables, and the profile
columns (`first_name`, `last_name`, `birth_date`, `gender`, `national_id`,
`email_verified_at`, `phone_verified_at`).

**Lock-free boot (B6.16).** Each DDL statement is checked against the catalog first and
only runs when its column / index / table / enum label is missing, the DDL of
concurrent processes (backend boot, seed jobs) is serialized by an advisory lock, and a
needed migration waits at most `lock_timeout = 10s` for its table lock — a restart no
longer blocks or deadlocks requests in flight.

**Client IP (B5.1a audit + B3.11 throttle).** `app/services/client_ip.py` is the
single resolver: the socket peer, or the `X-Forwarded-For` chain walked right to
left **only when the peer is listed in `TRUSTED_PROXIES`** (empty by default —
compose publishes the backend directly, so the header is client-controlled).
Put the backend behind a reverse proxy? Set `TRUSTED_PROXIES` to its address, or
every visitor shares one throttle bucket. Throttle knobs: `CONTACT_RATE_LIMIT`
(5), `CONTACT_RATE_WINDOW_SECONDS` (600).

## Tests

```bash
./.venv/bin/python -m pytest -q            # unit + live-DB integration tests
# tests/conftest.py defaults DATABASE_URL to the compose Postgres (B6.13); the
# integration tests skip cleanly when nothing answers there. Export DATABASE_URL
# to point them at another database.
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
