# Audit — 2026-09-19 — end-to-end flow on the Docker stack

## Task

Bring the Docker stack up and run the full **login → catalog → checkout →
payment** flow against the backend, fixing whatever breaks.

## What was done

1. **Stack up.** The Session-5 stack was still running the pre-switch build, so
   `docker compose up -d --build` rebuilt/recreated `backend`, `db-init` and
   `frontend` (postgres/minio stayed up). `db-init` re-ran the new seed chain:
   `seed_auth` (users existed) → `seed_products` (20 products) → `seed_demo`
   (2 addresses, 3 favorites; orders already present) → `seed_coupons`.
   Backend healthy, frontend ready on :5173, MinIO/postgres healthy.

2. **Bug fixed — `HTTPException` raised with two `detail`s.** `HTTPException`
   takes `detail` as its second positional arg, so
   `HTTPException(code, exc.message_fa, detail={...})` raised
   `TypeError: got multiple values for argument 'detail'` → **every**
   coupon/stock error during checkout returned **500** instead of a clean 4xx.
   Fixed in three places by passing a single object:
   - `routers/checkout.py` → `detail={"message", "code", "issues"}`
   - `routers/payments.py` (start + manual verify) → `detail={"message", "code"}`
   The frontend `api.ts` already reads `detail.message` for the toast and
   `detail.code/issues` for the stock-conflict list, so the contract holds.

3. **Full flow exercised against the live backend** (httpx, same endpoints the
   UI calls), all PASS:
   - signup (fresh user) → token; customer login as `customer@sande.local`
   - `GET /products` → 20 items with the expected shape
   - `POST /coupons/validate` → `SANDE10` = 69,000 off; unknown code → 404
   - `POST /checkout` → 200; `690,000 − 69,000 + 89,000 = **710,000**`,
     `coupon_applied = SANDE10`; reused coupon → **422 with `detail.message`**
     (previously 500)
   - stock conflict (product shrunk to 2, order 5) → **409 with
     `detail.code = stock_conflict` + `issues`** (previously 500); stock restored
   - `GET /orders/{id}/payment-session` → `SND-…` tracking code
   - `POST /orders/{id}/payment-complete` success → order **paid / processing**
     with items
   - `PATCH /auth/me`, `GET /payments/mine`
   - customer `GET /admin/stats` → **403**
   - admin login; `/admin/stats|orders|users|payments|refunds` → 200;
     `GET /products?include_inactive=true` → ≥20
   - storage: `/storage/upload-url` → presigned **PUT** → `/storage/sign`
     (upload signed, bundled asset key → `null`) → signed **GET** 200

4. **Frontend verified to serve the new code.** `GET :5173/` → 200 (SSR shell);
   Vite transforms `/src/routes/auth.tsx`, `/src/lib/api.ts`,
   `/src/lib/catalog.ts` → 200 with no errors in the container log;
   `VITE_API_URL` is injected as `http://localhost:8000`; CORS preflight from
   `http://localhost:5173` returns the expected `access-control-allow-*` headers
   and a cross-origin `GET /products` succeeds.

## Files changed

- `backend/app/routers/checkout.py` — single-`detail` `HTTPException`.
- `backend/app/routers/payments.py` — same fix (start + verify).
- `plan/audit/2026-09-19-e2e-flow-docker.md` (this file), `plan/session-log.md`,
  `plan/backend-tasks.md`.

## How to verify

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build
docker logs sandeh-db-init-1            # seed chain output
curl -sS localhost:8000/health
cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m pytest -q
# then reload http://localhost:5173 and sign in as
#   customer@sande.local / customer1234  or  admin@sande.local / admin1234
```

Backend unit tests: 19 passed; ruff clean; OpenAPI 35 paths.

## What is NOT done / open

- **No headless-browser click-through.** The flow was driven through the same
  HTTP endpoints the UI calls (plus SSR/module/CORS checks); no real browser
  session was automated, so client-only rendering paths (react-query hydration,
  toasts) are not exercised end to end.
- **Real Zarinpal redirect** still not wired (the page uses the simulated
  gateway endpoints).
- **No regression test** was added for the `HTTPException` bug — the router
  suite still needs the DB fixture from B3.5.
- The run created **dev data on purpose**: a few test customers
  (`flowtest+…`, `stocktest+…`), extra orders, and one MinIO object.

## Data left behind (dev stack)

- New users `flowtest+<ts>@sande.local`, `stocktest+<ts>@sande.local`.
- Several paid/pending test orders; `tshirt-1` stock decremented.
- One `audit.jpg` object in the `product-images` bucket.
