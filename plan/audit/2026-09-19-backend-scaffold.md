# Audit — 2026-09-19 — Backend scaffold + core MVP (B1.1 → B1.8)

## Task

Set up the Python backend service for the SÂNDÉ store as a sibling folder
`backend/` and implement the lean-MVP scope chosen by the user from Part 7 of
FEATURES.md: real coupons, Zarinpal payments, transactional stock decrement,
product search — with Supabase JWT auth and direct Postgres access.

## What was done

- **Scaffold**: `pyproject.toml` (fastapi, uvicorn, sqlalchemy[asyncio], asyncpg,
  pydantic-settings, httpx, python-jose), `.env.example` documenting every env
  var, `.gitignore`, `README.md` with setup + API table.
- **DB layer** (`app/db.py`, `app/models.py`): async engine against the Supabase
  Postgres; SQLAlchemy models mirroring products/orders/order_items/payments;
  idempotent startup DDL creating the new `coupons` and `coupon_redemptions`
  tables only (existing Supabase tables are never touched by DDL).
- **Auth** (`app/auth.py`): `Authorization: Bearer <supabase-jwt>` verified
  HS256 with `aud=authenticated`; role read from `public.user_roles`;
  `CurrentUser` / `AdminUser` dependencies (admin guard → 403).
- **Coupons** (`app/services/coupons.py`, `app/routers/coupons.py`): percent or
  amount off, min subtotal, expiry window, global + per-user caps; redemption
  recorded with the coupon row locked `FOR UPDATE` inside the checkout
  transaction; admin CRUD + code generator; seed script `app/seed_coupons.py`
  (SANDE10 = 10%, WELCOME500 = 50,000 off ≥ 500,000).
- **Checkout** (`app/services/checkout.py`, `app/routers/checkout.py`): one
  transaction — lock product rows (sorted ids to avoid deadlocks) → validate
  active/size/stock → server-side prices only → coupon → insert order + items →
  guarded `UPDATE … SET stock = stock - qty WHERE stock >= qty`. Raises
  `stock_conflict` with an issues list the UI can render.
- **Payments** (`app/services/payments.py`, `app/routers/payments.py`): Zarinpal
  v4 request/verify + StartPay redirect; pending `payments` row keyed by
  authority; callback verifies and flips order to `paid/processing`, payment to
  `succeeded`, then 303-redirects to `FRONTEND_URL/payment/{orderId}?verify=…`;
  simulation mode when no merchant id is set (zero-UUID); `POST
  /payments/verify` for polling clients. Existing conventions preserved
  (`SND-…`, `unpaid/paid/refunded`, `pending/succeeded/failed`).
- **Search** (`app/services/search.py`, `app/routers/search.py`): ranked ILIKE
  over name/category/description/material, `COUNT(*) OVER()` total, limit/offset.
- **Pricing** (`app/services/pricing.py`): mirrors cart rules — shipping
  ۸۹٬۰۰۰, free ≥ ۲٬۰۰۰٬۰۰۰, discount capped at subtotal.
- **Quality**: 19 pytest unit tests (pricing, coupon rules, helpers) — all
  pass; `ruff check` clean; TestClient smoke test: `/health` 200, 11 routes,
  unauthenticated `/checkout` → 401.

## Files changed (all new, under `backend/`)

```
backend/pyproject.toml
backend/.env.example
backend/.gitignore
backend/README.md
backend/app/__init__.py
backend/app/main.py
backend/app/config.py
backend/app/db.py
backend/app/models.py
backend/app/auth.py
backend/app/schemas.py
backend/app/seed_coupons.py
backend/app/services/__init__.py
backend/app/services/pricing.py
backend/app/services/coupons.py
backend/app/services/checkout.py
backend/app/services/payments.py
backend/app/services/search.py
backend/app/routers/__init__.py
backend/app/routers/health.py
backend/app/routers/search.py
backend/app/routers/stock.py
backend/app/routers/coupons.py
backend/app/routers/checkout.py
backend/app/routers/payments.py
backend/tests/test_pricing_and_coupons.py
```

## How to verify

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill DATABASE_URL + SUPABASE_JWT_SECRET
.venv/bin/python -m pytest tests/ -q          # 19 passed
.venv/bin/ruff check app/                     # All checks passed!
DATABASE_URL=… SUPABASE_JWT_SECRET=… .venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
print(c.get('/health').json())                 # {'ok': True, …}
"
# with real env: uvicorn app.main:app --reload --port 8000 → http://localhost:8000/docs
```

## What is NOT done / open

- Frontend not wired (see `frontend-tasks.md` F1.1–F1.7) — cart/checkout/payment
  still run the old Supabase-only path.
- Coupon tables exist only via startup DDL; a proper migration file in
  `vogue-vintage-vibes/supabase/migrations/` is still recommended (and RLS
  policies for the new tables if any client reads them directly).
- No DB integration tests against live Postgres; no CI.
- B2.x features (notifications, reports/Excel, PDF invoices, recommendations,
  webhooks/jobs) not started.
