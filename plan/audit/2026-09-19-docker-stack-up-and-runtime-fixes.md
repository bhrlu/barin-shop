# Audit — 2026-09-19 — docker stack up + runtime fixes

## Task

User request: "now up the front end and backend in docker" — start
`infra/docker-compose.yml` for real (Session 2 never ran it end to end) and make it
work.

## What was done

### Setup

- Created `infra/.env` (gitignored) from `.env.example` with a generated `JWT_SECRET`.
- Checked for port conflicts first: an unrelated project (`tadarok-*`) is already
  running on 5433 / 8001 / 9002 / 9003 / 8080 / 6380, so this stack's defaults
  (5432, 8000, 5173, 9000, 9001) are all free.

### Image problem: MinIO is gone from Docker Hub

MinIO stopped publishing free Docker Hub images in October 2025, so
`minio/mc:latest` **and** `minio/minio:latest` both fail with
`pull access denied ... repository does not exist`. The locally cached
`minio/minio:latest` (from the other project) masked this.

Fix: switch to `quay.io/minio/minio:latest` (verified to pull) and drop the
standalone `mc` image entirely — the server image already ships `/usr/bin/mc`,
so `minio-init` reuses it.

### Runtime bugs found by actually running the stack

All eight were in the unlogged Session-3 code and none was covered by the 19 unit
tests (which only exercise pure logic).

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `db-init` exits 1: `relation "public.coupons" does not exist` | `seed_coupons` ran before anything created the coupon tables (only the API's startup DDL creates them) | `seed_coupons` now calls `startup_ddl()` itself |
| 2 | **Every** password hash/verify raised `ValueError: password cannot be longer than 72 bytes` | passlib 1.7.4 (unmaintained since 2020) cannot load bcrypt ≥ 4.1: its backend probe hashes a >72-byte secret | dropped passlib, use `bcrypt` directly (still standard `$2b$`), truncate at 72 bytes consistently |
| 3 | `db-init` exits 1: `coupon_redemptions` creation failed | its DDL still referenced `auth.users`, deleted with Supabase in Session 3 | reference `public.users` |
| 4 | `GET /search` → 500 `AmbiguousParameterError: could not determine data type of parameter $2` | `(:category IS NULL OR category = :category)` gives asyncpg no type to infer | `CAST(:category AS text) IS NULL` |
| 5 | `GET /admin/stats` → 500 `syntax error at or near "FILTER"` | `COALESCE(SUM(total), 0) FILTER (...)` — FILTER must attach to the aggregate, not the COALESCE | `COALESCE(SUM(total) FILTER (...), 0)` |
| 6 | `POST /storage/upload-url` → 502 | minio-py requires `timedelta` for `expires`; an int raises `AttributeError: int has no attribute total_seconds` | pass `timedelta(hours=1)` / `timedelta(days=7)` |
| 7 | Presigned URLs were signed for `minio:9000` — unreachable from the browser, and unreachable *from the client* once pointed at `localhost:9000` | the host is part of the signature, and minio-py resolves the bucket region with a network call unless a region is given | sign for `MINIO_PUBLIC_ENDPOINT`, pass `region` so signing is offline |
| 8 | Payment callback always 404 — order never became paid | `verify_and_finalize` overwrites `reference` (which held the authority) with the `SND-…` code, then the router looked the payment up by `reference = authority` | `verify_and_finalize` returns `order_id`; the router uses it |

### Verified end to end (against the running stack)

- Containers: postgres + minio healthy, `minio-init` and `db-init` exit 0,
  backend healthy, frontend serving (Vite 8.2.0, SSR connected, HTTP 200).
- Seeds: `admin@sande.local` / `customer@sande.local`, `SANDE10` + `WELCOME500`,
  bucket `product-images` created with public read.
- API: login → JWT (`/auth/me` returns role `admin`); 401 without a token; **403**
  for a customer on every `/admin/*` route; `/products` (20 seeded), `/search`
  (5 hits, category filter, 0 on no match), `/coupons` + `/coupons/validate`
  (SANDE10 → 80,000 off 800,000), `/orders`, `/favorites`, `/addresses`,
  `/admin/{stats,orders,payments,users,refunds}` all 200.
- Storage: presigned PUT from the host → **200**, public GET → 200, presigned GET
  via `/storage/sign` → 200.
- Full purchase: checkout (subtotal 1,380,000 → discount 138,000 → shipping 89,000
  → total 1,331,000, coupon recorded) → stock 25 → 23 → `/payments/start`
  (simulation authority) → callback → **303** to
  `…/payment/<id>?verify=paid&ref=SND-26091899762-209041` → order
  `processing / paid`. Cancelled path → **303** `verify=failed`, order left
  `pending / unpaid`.
- `ruff check` clean, `pytest` 19 passed.

## Files changed

- `infra/docker-compose.yml` — quay.io MinIO for both services, `minio-init` reuses
  the server image, `MINIO_PUBLIC_ENDPOINT` for the backend
- `infra/.env.example` — documented `MINIO_PUBLIC_ENDPOINT`
- `infra/.env` — **new, gitignored** (generated dev secret)
- `backend/pyproject.toml` — `passlib[bcrypt]` → `bcrypt`
- `backend/app/security.py` — direct bcrypt hashing
- `backend/app/config.py` — `minio_region`
- `backend/app/db.py` — coupon DDL points at `public.users`
- `backend/app/seed_coupons.py` — creates its own tables first
- `backend/app/services/search.py` — `CAST(:category AS text)`
- `backend/app/routers/admin.py` — FILTER inside the aggregate
- `backend/app/routers/storage.py` — timedelta, public host, explicit region
- `backend/app/services/payments.py`, `backend/app/routers/payments.py` — return
  `order_id` from verification

## How to verify

```bash
cp infra/.env.example infra/.env      # fill JWT_SECRET if starting fresh
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build
docker compose -f infra/docker-compose.yml --env-file infra/.env ps -a

curl -s localhost:8000/health
# login (password hashing — bug 2)
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"admin@sande.local","password":"admin1234"}'
curl -s 'localhost:8000/search?q=%D8%AA%DB%8C%E2%80%8C%D8%B4%D8%B1%D8%AA'   # bug 4
```

- store → http://localhost:5173 · API docs → http://localhost:8000/docs ·
  MinIO console → http://localhost:9001 (`sande` / `sande-secret`)

## What is NOT done / open

- **Repeat payment callback returns 400 instead of `already_paid`.** After a
  successful verify the row no longer holds the authority, so the session cannot be
  found a second time and the `already_paid` branch is unreachable. Fixing it
  properly means persisting the authority separately from `reference` — a
  `payments.authority` column (schema change) — so it is left as a decision.
- **The 19 tests still cover only pure logic.** None of the eight bugs above was
  caught by a test; the new routers have no coverage (task B3.5).
- Frontend still runs on Supabase (`src/lib/api.ts` is unused) — the migration
  itself is still open (F1.2–F1.7).
- Stale readers still outstanding: `backend/README.md`, `infra/README.md`,
  `app/db.py`-adjacent comments (B3.2–B3.4).
- **Local test data was created on purpose** while verifying: 2 orders (one
  `processing/paid`, one `pending/unpaid`), stock on `tshirt-1` reduced 25 → 23,
  and one `uploads/…jpg` object in the `product-images` bucket.
- This is a dev stack only: no TLS, no production compose, simulation-mode payments.
