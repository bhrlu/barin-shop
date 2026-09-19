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
│   ├── seed_auth.py       # bootstrap admin + demo customer
│   ├── seed_products.py   # 20-product catalog (idempotent)
│   ├── seed_demo.py       # demo addresses/favorites/orders
│   ├── seed_coupons.py    # SANDE10 + WELCOME500
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
python -m app.seed_auth       # bootstrap admin + demo customer
python -m app.seed_products   # 20 catalog products
python -m app.seed_coupons    # starter coupons
uvicorn app.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs.

> `DATABASE_URL` must use the **asyncpg** driver
> (`postgresql+asyncpg://…`) — bare `postgresql://` fails (`psycopg2` not installed).
> The compose stack in `infra/` is the easiest way to get a database + MinIO.

## Auth model

The service issues **its own HS256 JWTs** via `/auth/login` (bcrypt-hashed
passwords in `public.users`). Every user endpoint requires
`Authorization: Bearer <token>`; the role is resolved from `public.user_roles`
(DB is source of truth, token claim is the fallback). Admin routes return 403 for
non-admins. `OptionalUser` resolves a caller when present but stays anonymous
otherwise (used to personalise search history).

## API summary

Public / customer:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | liveness (used by the compose healthcheck) |
| POST | `/auth/signup` · `/auth/login` | – | register / sign in → token |
| GET/PATCH | `/auth/me` | user | profile read / update |
| GET | `/products` | optional | catalog list — filters `category, tag, badge, availability, on_sale, size, color, min_price, max_price` + `sort` |
| GET | `/products/compare?ids=` | – | side-by-side comparison |
| GET | `/products/{id}` | – | one product (with `avg_rating`, `review_count`) |
| GET | `/products/{id}/related` · `/recommendations` | – | discovery |
| GET | `/products/{id}/variants` | – | per size×color stock |
| GET/POST | `/products/{id}/reviews` | – / user | reviews + rating summary |
| DELETE | `/reviews/{id}` | user | delete own review |
| POST | `/products/{id}/view` · GET `/recently-viewed` | user | view tracking |
| GET | `/search?q=` · `/search/suggest` | optional | search + autocomplete |
| GET/DELETE | `/search/history` | user | recent searches |
| POST | `/stock/check` | – | pre-check cart lines (variant-aware) |
| POST | `/coupons/validate` | user | validate a code against a subtotal |
| POST | `/checkout` | user | create order (stock-locked, coupon applied) |
| GET | `/orders` · `/orders/{id}` | user | my orders / one order |
| POST | `/orders/{id}/cancel` · `/refunds` | user | cancel / refund request |
| GET | `/orders/{id}/payment-session` | user | simulated gateway session |
| POST | `/orders/{id}/payment-complete` | user | simulated gateway callback |
| GET | `/payments/mine` | user | payment history |
| POST | `/payments/start` · `/payments/verify` | user | real Zarinpal session / verify |
| GET | `/payments/zarinpal/callback` | – | gateway return (redirects to the frontend) |
| GET/POST/DELETE | `/addresses` | user | address book |
| GET/POST | `/favorites` · `/favorites/{id}` | user | wishlist |
| POST | `/storage/upload-url` · `/storage/sign` | admin / user | MinIO presign |

Admin:

| Method | Path | Purpose |
|---|---|---|
| POST/PATCH/DELETE | `/products` · `/products/{id}` | product CRUD (soft-delete if ordered) |
| POST/PATCH/DELETE | `/products/{id}/variants` · `/variants/{id}` | variant stock CRUD |
| GET/PATCH | `/admin/reviews` · `/reviews/{id}` | moderation + seller reply |
| GET | `/admin/inventory` · `/admin/inventory/low-stock` | stock health / alerts |
| GET | `/admin/stats` · `/users` · `/orders` · `/payments` · `/refunds` | dashboards |
| PATCH | `/refunds/{id}` | resolve a refund request |
| POST/GET/PATCH | `/coupons` · `/coupons/{id}` · `/coupons/generate` | coupon CRUD |

## Stock model

`products.stock` is the aggregate; optional `product_variants` rows hold stock
per **size × color**. When a variant exists for a combination it is
**authoritative** (its own `active` flag can disable a single combination);
otherwise the product's aggregate stock applies. Checkout locks rows `FOR UPDATE`
and decrements with a guarded `UPDATE … WHERE stock >= qty` so nothing can
oversell. Shared by `POST /stock/check` and checkout via `app/services/variants.py`.

## Catalog DDL

The coupon **and** catalog tables/columns are created idempotently on startup
(`app/db.py`), so a fresh database and an already-seeded one both converge. The
base schema comes from `infra/initdb/`; this service owns only the additive
columns and the `coupons`, `product_variants`, `product_reviews`,
`search_history`, `recently_viewed` tables.

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
See `plan/frontend-tasks.md` Milestone F3 for the catalog UI still to be wired.
