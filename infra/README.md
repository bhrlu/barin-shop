# SÂNDÉ — infra (local Docker dev stack)

Lightweight stack that runs both halves of the project in containers:

```
infra/
├── docker-compose.yml      # postgres + minio + backend + frontend + init jobs
├── backend.Dockerfile      # FastAPI (python:3.12-slim, uvicorn --reload)
├── frontend.Dockerfile     # TanStack Start dev server (oven/bun, vite dev)
├── .env.example            # copy to .env and fill in
└── initdb/
    └── 02-public-schema.sql # the local schema + 20-product seed (applied on first start)
```

## What runs where

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:16-alpine | 5432 | The backend's database (`public.users` is a real table with bcrypt hashes) |
| `minio` | quay.io/minio/minio | 9000 (API) / 9001 (console) | S3-compatible object storage |
| `minio-init` | quay.io/minio/minio | – | One-shot: creates the public-read `product-images` bucket |
| `db-init` | backend image | – | One-shot: `seed_auth → seed_products → seed_demo → seed_coupons` |
| `backend` | FastAPI | 8000 | The sole backend — docs at `/docs` |
| `frontend` | Vite dev server (Bun) | 5173 | The store UI with hot reload |

## No Supabase

The FastAPI service is the **only** backend: it owns auth (own HS256 JWTs),
data, and object storage (MinIO). The frontend talks to it directly via
`VITE_API_URL`; there is no Supabase project, URL, or key in the stack.

## Quick start

```bash
cp infra/.env.example infra/.env        # JWT_SECRET is required
docker compose -f infra/docker-compose.yml up -d --build
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
  Re-apply from scratch with `docker compose -f infra/docker-compose.yml down -v`
  (⚠ wipes local DB data).
- **Schema:** base tables come from `infra/initdb/`. The backend adds the coupon
  and catalog tables/columns **idempotently at startup** (`app/db.py`), so no
  migration step is needed on an existing volume.
- **MinIO image comes from `quay.io`** — MinIO stopped publishing free images on
  Docker Hub in Oct 2025. `minio-init` reuses the server image's bundled `mc`
  (the standalone `minio/mc` image is also gone).
- **Presigning uses the browser host.** `MINIO_PUBLIC_ENDPOINT` (default
  `localhost:9000`) is what gets signed; signing for the in-cluster `minio:9000`
  would fail the browser with `SignatureDoesNotMatch`.
- **Hot reload:** backend source (`../backend/app`) and frontend source
  (`../vogue-vintage-vibes`) are bind-mounted; the frontend image's
  `node_modules` is preserved via a named volume.
- **Payments:** with the default `ZARINPAL_MERCHANT_ID` (zero UUID) the backend
  stays in simulation mode — no real gateway calls. The payment page also uses the
  backend's simulated `payment-session` / `payment-complete` endpoints.
- The stack is for **development**; no TLS, default passwords, published ports.
