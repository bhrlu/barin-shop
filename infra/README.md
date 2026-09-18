# SÂNDÉ — infra (local Docker dev stack)

Lightweight stack that runs both halves of the project in containers:

```
infra/
├── docker-compose.yml      # postgres + minio + backend + frontend + init jobs
├── backend.Dockerfile      # FastAPI (python:3.12-slim, uvicorn --reload)
├── frontend.Dockerfile     # TanStack Start dev server (oven/bun, vite dev)
├── .env.example            # copy to .env and fill in
└── initdb/                 # applied on FIRST postgres start only
    ├── 01-auth-shim.sql    # local auth schema + roles so Supabase SQL applies
    └── 02-public-schema.sql# the 4 Supabase migrations + 20-product seed
```

## What runs where

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:16-alpine | 5432 | Backend's database. Local mirror of the Supabase schema (products/orders/payments/coupons…) |
| `minio` | minio/minio | 9000 (API) / 9001 (console) | S3-compatible object storage, `product-images` bucket auto-created |
| `minio-init` | minio/mc | – | One-shot: creates the public-read bucket |
| `db-init` | backend image | – | One-shot: coupon DDL + seeds SANDE10 / WELCOME500 |
| `backend` | FastAPI | 8000 | Coupons, checkout, stock, payments, search — docs at `/docs` |
| `frontend` | Vite dev server (Bun) | 5173 | The store UI with hot reload |

## Supabase stays hosted (by design)

Per the session-1 decision, auth/data/storage keep using the hosted Supabase
project; the containers give the **backend** a real local Postgres and give
both apps local ports. The frontend container still needs
`VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY` for login/product data.

## Quick start

```bash
cp infra/.env.example infra/.env        # fill SUPABASE_* values
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build
```

- Store: http://localhost:5173
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (credentials in `infra/.env`)

> `docker compose` automatically loads `infra/.env` when run from inside
> `infra/`; from the repo root pass `--env-file infra/.env` (or export the vars).

## Frontend build note (lovable tarball)

`bun.lock` pins `@lovable.dev/vite-tanstack-config` to a tarball URL that only
resolves inside Lovable's sandbox (403 elsewhere). `infra/frontend.Dockerfile`
injects a temporary `overrides` entry pinning the same version (2.13.1) to the
public npm registry — it does not modify the repo's `package.json` or lockfile.
If Lovable ever publishes it publicly, the override can be deleted.

## Notes & gotchas

- **First run only:** `initdb/*.sql` runs when the `pgdata` volume is empty.
  To re-apply from scratch: `docker compose down -v` (⚠ wipes local DB data).
- **Coupon tables** are created idempotently by the backend at startup
  (`app/db.py`), same as in production — `db-init` just also seeds coupons.
- **Hot reload:** backend source (`../backend/app`) and frontend source
  (`../vogue-vintage-vibes`) are bind-mounted; the frontend image's
  `node_modules` is preserved via a named volume.
- **Payments:** with the default `ZARINPAL_MERCHANT_ID` (zero UUID) the
  backend stays in simulation mode — no real gateway calls.
- **Local Postgres ≠ hosted Supabase:** users created in the hosted project
  won't exist in the local `auth.users` shim. Backend endpoints called with
  hosted-project JWTs still verify (same `SUPABASE_JWT_SECRET`) but role
  lookup falls back to `customer` unless the user row is inserted locally.
- The stack is for **development**; no TLS, default passwords, published ports.
