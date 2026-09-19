# Audit — 2026-09-19 — catalog seed + full frontend cut-over

## Task

Two user requests, done in order:

1. **Create a seed from the data that lives in Supabase on the frontend side**
   (the 20-product catalog), plus demo data, so the backend owns its own seed.
2. **Connect the frontend to the backend** — the user chose a **full switch**:
   every Supabase import replaced by `src/lib/api.ts`, with a **persistent,
   resumable checklist** updated after each API connection so a new session can
   continue.

## What was done

### Backend — seeds

- **`app/seed_products.py`** (new) — the 20 starter products, transcribed from
  the frontend's Supabase migration (`20260810233223_*.sql`) /
  `src/data/products.ts`. Idempotent (`ON CONFLICT (id) DO NOTHING`), stock 25,
  asset-key image references. Works on any database, not only one created by the
  compose initdb.
- **`app/seed_demo.py`** (new) — for `customer@sande.local`: two addresses,
  three favorites, and two orders (one paid `delivered`, one `unpaid pending`)
  with order items and a payment row. Skips sections that already have rows, and
  skips cleanly if the customer/product seeds have not run.
- **`infra/docker-compose.yml`** — `db-init` now runs
  `seed_auth → seed_products → seed_demo → seed_coupons`.

### Backend — endpoints needed by the switch

- **`PATCH /auth/me`** (`routers/auth.py`, `ProfileUpdateIn` in `schemas.py`) —
  profile save for the account page (replaces the Supabase `profiles.upsert`).
- **`GET /payments/mine`** (`routers/payments.py`) — the caller's payment
  history with `order_number` (replaces the account payments join).

Surface: 34 → **35 paths**. `pytest` → 19 passed; `ruff` clean.

### Frontend — full cut-over

Single data layer:

- **`src/lib/api.ts`** — extended into the one client: token storage + `ApiError`,
  and typed methods for auth (+`updateMe`), products (+admin CRUD), coupons
  (`validateCoupon`), checkout, stock check, addresses, favorites, orders
  (+cancel/refund/patch/payment-session/payment-complete), `myPayments`,
  `/admin/*`, storage (`uploadImage`, `signStorage`), search.

Wiring, file by file:

- **Auth/session** — `src/lib/auth.tsx` rewritten around the backend JWT
  (`UserInfo`, `signIn`/`signUp`/`signOut`/`refresh`); `_authenticated/route.tsx`
  guards on `getToken()` + `api.me()`; `routes/auth.tsx` sign-in/sign-up on the
  backend, **Google OAuth removed** (backend has no OAuth); `start.ts` no longer
  registers the Supabase auth-attacher.
- **Catalog/images** — `src/lib/catalog.ts` reads `GET /products` and signs
  `uploads/…` via `POST /storage/sign`; `ProductImageManager` uploads through
  `POST /storage/upload-url`.
- **Cart/checkout** — `routes/cart.tsx` validates the coupon via
  `POST /coupons/validate` (hardcoded `SANDE10` gone) and stashes only the code
  in `sessionStorage`; `routes/checkout.tsx` calls `POST /checkout`, surfaces
  `stock_conflict` issues, and redirects by `order_id`.
- **Payment/cancel** — `payment.$orderId.tsx` uses
  `GET /orders/{id}/payment-session` + `POST /orders/{id}/payment-complete`;
  `CancelOrderButton` calls `POST /orders/{id}/cancel`.
- **Account** — orders, order detail (`items` instead of `order_items`),
  addresses, favorites, payments, profile all on the backend.
- **Admin** — dashboard (`/admin/stats`), orders (`/admin/orders`, `PATCH
  /orders/{id}`), products (`GET/POST/PATCH/DELETE /products`), users
  (`/admin/users`).
- **Removed** — `src/integrations/supabase/*`, `src/integrations/lovable/*`,
  `src/lib/order-actions.functions.ts`, `src/lib/payment.functions.ts`;
  `src/lib/orders.ts` keeps only the status label maps. No `@supabase/supabase-js`
  import remains (the `package.json` entry is left in place to avoid churn in the
  lockfile).

## Files changed

Backend: `app/routers/auth.py`, `app/routers/payments.py`, `app/schemas.py`,
`app/seed_products.py` (new), `app/seed_demo.py` (new).

Infra: `docker-compose.yml`.

Frontend (modified): `src/lib/api.ts`, `src/lib/auth.tsx`, `src/lib/catalog.ts`,
`src/lib/favorites.ts`, `src/lib/orders.ts`, `src/start.ts`,
`src/routes/auth.tsx`, `src/routes/cart.tsx`, `src/routes/checkout.tsx`,
`src/routes/_authenticated/{route,account,account.index,account.orders,account.order.$orderId,account.addresses,account.payments,payment.$orderId,admin.index,admin.orders,admin.products,admin.users}.tsx`,
`src/components/CancelOrderButton.tsx`,
`src/components/admin/ProductImageManager.tsx`.

Frontend (deleted): `src/integrations/supabase/*`, `src/integrations/lovable/*`,
`src/lib/order-actions.functions.ts`, `src/lib/payment.functions.ts`.

Docs: `plan/frontend-tasks.md` (F1 rewritten as the resumable tracker), this file.

## How to verify

```bash
# backend unit tests + lint
cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check .

# API surface (34 → 35 paths)
DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db" JWT_SECRET="x" \
  .venv/bin/python -c "import app.main; print(len(app.main.app.openapi()['paths']))"

# frontend typecheck + lint of the changed set (deps installed locally)
cd vogue-vintage-vibes && npx tsc --noEmit
npx eslint src/lib/api.ts src/lib/auth.tsx src/lib/catalog.ts src/lib/favorites.ts \
  src/lib/orders.ts src/start.ts src/routes/auth.tsx src/routes/cart.tsx \
  src/routes/checkout.tsx src/routes/_authenticated src/components/CancelOrderButton.tsx \
  src/components/admin/ProductImageManager.tsx

# seeds (needs a live DB)
cd backend && python -m app.seed_auth && python -m app.seed_products \
  && python -m app.seed_demo && python -m app.seed_coupons
```

`tsc --noEmit` → **0 errors**. ESLint on the changed set → only pre-existing
`react-hooks`/`react-refresh` warnings; the two remaining prettier errors are in
untouched files (`account.favorites.tsx`, `admin.tsx`) and predate this change.

## What is NOT done / open

- **No end-to-end run.** The stack was not started, so login → catalog → cart →
  checkout → payment has not been exercised against a live backend in this task.
- **Real Zarinpal redirect** is not wired — the payment page uses the backend's
  simulated gateway endpoints (same UX as before). See F1/A1 in `frontend-tasks.md`.
- **Google/OAuth login** is gone with Supabase (no backend OAuth yet).
- **F1.5 search bar, F1.6 live stock, F1.7 admin stock** remain open.
- **Baseline lint debt** in untouched frontend files (prettier) still fails a
  repo-wide `eslint .`; not fixed here to keep the diff scoped.
- `@supabase/supabase-js` is still a `package.json` dependency (unused); removing
  it would churn `bun.lock`.
