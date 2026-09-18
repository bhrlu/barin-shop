# SÂNDÉ Backend (FastAPI)

Python backend service for the SÂNDÉ store — sits **next to** the TanStack Start frontend
and the Supabase database, and fills the gaps listed in Part 7 of `FEATURES.md`:

| Feature | Where |
|---|---|
| **Real coupon system** | `app/routers/coupons.py`, `app/services/coupons.py` (+ new `coupons` / `coupon_redemptions` tables) |
| **Real payment gateway (Zarinpal)** | `app/routers/payments.py`, `app/services/payments.py` (simulation mode without merchant id) |
| **Transactional stock decrement** | `app/services/checkout.py` — `FOR UPDATE` locks + guarded decrement, no oversell |
| **Product search** | `app/routers/search.py`, `app/services/search.py` |

## Layout

```
backend/
├── pyproject.toml         # deps: fastapi, sqlalchemy, asyncpg, httpx, python-jose …
├── .env.example           # DATABASE_URL, SUPABASE_JWT_SECRET, ZARINPAL_*, URLs
└── app/
    ├── main.py            # FastAPI app + CORS + Zarinpal Status mapping
    ├── config.py          # pydantic-settings
    ├── db.py              # async engine + idempotent coupon-table DDL
    ├── models.py          # SQLAlchemy models (Supabase tables + coupons)
    ├── auth.py            # Supabase JWT verification + admin/customer roles
    ├── schemas.py         # pydantic request/response models
    ├── seed_coupons.py    # seeds SANDE10 + WELCOME500
    ├── services/          # business logic (coupons, checkout, payments, search, pricing)
    └── routers/           # HTTP layer (health, search, stock, coupons, checkout, payments)
```

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then fill in DATABASE_URL + SUPABASE_JWT_SECRET
python -m app.seed_coupons  # optional starter coupons
uvicorn app.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs

### Where to get the values

- `DATABASE_URL` — Supabase Dashboard → Project Settings → Database → Connection string
  (use the pooler URI; port 5432 for a long-lived server).
- `SUPABASE_JWT_SECRET` — Supabase Dashboard → Project Settings → API → JWT Settings.
- `ZARINPAL_MERCHANT_ID` — zarinpal.com panel; leave the zero UUID for simulation mode.

## Auth model

All user endpoints require `Authorization: Bearer <supabase_access_token>`.
The token is verified (HS256, `aud=authenticated`) and the role is loaded from
`public.user_roles`. Admin endpoints (coupon CRUD) additionally require the
`admin` role → 403 otherwise.

## API summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | liveness |
| GET | `/search?q=تی‌شرت&category=tshirt&limit=20&offset=0` | user | text search (name/description/material/category) |
| POST | `/stock/check` | user | pre-check cart lines against live stock, returns server-price subtotal |
| POST | `/coupons/validate` | user | validate code against subtotal → `{ code, discount, … }` |
| POST | `/checkout` | user | create order (stock-locked, coupon applied) → order summary |
| POST | `/payments/start` | user | open a Zarinpal session → `{ authority, redirect_url, amount }` |
| GET | `/payments/zarinpal/callback` | – (gateway) | verify + finalize, redirect to frontend |
| POST | `/payments/verify` | user | manual verify for polling clients |
| POST | `/coupons` · GET `/coupons` · PATCH `/coupons/{id}` · POST `/coupons/generate` | admin | coupon CRUD |

## Frontend integration sketch

```ts
// validate coupon in the cart page (replaces the hardcoded SANDE10)
const res = await fetch(`${BACKEND_URL}/coupons/validate`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${supabaseSession.access_token}`,
  },
  body: JSON.stringify({ code, subtotal }),
});
```

Checkout calls `POST /checkout`, then `POST /payments/start` and
`window.location.assign(redirect_url)`. The callback sends the shopper back to
`FRONTEND_URL/payment/{orderId}?verify=paid&ref=…` — the existing payment page.
