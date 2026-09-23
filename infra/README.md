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
| `db-init` | backend image | – | One-shot **migrator** (B5.1e): runs `startup_ddl()` (schema + the DML-only app role), then `seed_auth → seed_products → seed_demo → seed_coupons` |
| `backend` | FastAPI | 8000 | The sole backend — docs at `/docs`. Runs no DDL; connects as the DML-only app role |
| `frontend` | Vite dev server (Bun) | 5173 | The store UI with hot reload |
| `worker` | backend image | – | B2.5 background jobs (`python -m app.worker`): outbox sweeper + abandoned-payment reminders every `JOBS_INTERVAL_SECONDS`. No hot reload — `docker compose restart worker` after changing `app/services/jobs.py`; one manual pass: `docker compose exec worker python -m app.worker --once` |
| `tools` | backend image | – | Profile `tools`, never started by `up`: ad-hoc DDL / extra seeds **as the schema owner** — `docker compose run --rm tools python -m app.seed_mock` |

> Want the admin screens populated? After the stack is up, run the optional demo
> dataset through the owner-side `tools` service: `docker compose -f
> infra/docker-compose.yml run --rm tools python -m app.seed_mock` (8 customers, 31
> backdated orders, refund claims in every state, reviews, inbox, variants).
> Idempotent — safe to re-run.

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

## Frontend build note (lovable tarball — resolved)

`bun.lock` used to pin `@lovable.dev/vite-tanstack-config` to a tarball URL that
only resolved inside Lovable's sandbox (403 elsewhere). Since 2026-09-21 the
lockfile resolves all 10 formerly-private packages from `registry.npmjs.org`
(identical tarballs/SRI hashes), so the image just runs plain `bun install` — the
`overrides` injection was removed from `frontend.Dockerfile`. If the lockfile ever
regresses to a private tarball URL, the build fails loudly at `bun install`.

## Notes & gotchas

- **First run only:** `initdb/*.sql` runs when the `pgdata` volume is empty.
  Re-apply from scratch with `docker compose -f infra/docker-compose.yml down -v`
  (⚠ wipes local DB data).
- **Schema:** base tables come from `infra/initdb/`. Everything the API owns on top
  of them (coupons, catalog, notifications, profile, the audit/inventory triggers …)
  is created **idempotently by the `db-init` job** via `startup_ddl()` (`app/db.py`),
  so no manual migration step is needed on an existing volume — `docker compose up -d
  --build db-init` re-converges one (the job uses the image's copy of `app/`, so a
  local `db.py` change needs the rebuild). There is no migration framework by design.
- **Database roles (B5.1e).** Two roles: the **migrator** (`POSTGRES_USER`, the
  schema owner and image superuser) runs `db-init`/`tools`; the **application role**
  (`DATABASE_APP_USER`, default `sande_app`) is what `backend` and `worker` connect
  with — rows access only, no DDL, owns nothing, and it cannot disable the
  append-only triggers. `db-init` creates and grants it, and `backend` waits for that
  job (`service_completed_successfully`) because the API no longer creates its own
  schema. The backend container never receives the owner credentials, so ad-hoc DDL
  goes through `tools` (`docker compose run --rm tools …`). Check it from the
  outside: `docker exec -e PGPASSWORD=sande-app sandeh-postgres-1 psql -U sande_app
  -d postgres -c 'SELECT current_user, rolsuper FROM pg_roles WHERE rolname =
  current_user'` → `sande_app | f`.
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
- **Client IP / reverse proxies (B3.11).** The backend port is published directly,
  so `X-Forwarded-For` is ignored unless the socket peer is listed in
  `TRUSTED_PROXIES` (empty by default). In docker every host request arrives from
  the bridge gateway (e.g. `172.23.0.1`), so the local browser and `api_smoke.py`
  share one contact-form bucket (5 attempts / 10 min); to reset it during
  development: `docker exec sandeh-postgres-1 psql -U sande -d postgres -c
  "DELETE FROM contact_attempts"`. Behind a real reverse proxy, set
  `TRUSTED_PROXIES` to the proxy's address.
- **Notifications (B2.1).** In-app notifications need no configuration. SMS
  (`KAVENEGAR_API_KEY`, `KAVENEGAR_SENDER`) and email (`SMTP_HOST`, `SMTP_PORT`,
  `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`, `SMTP_SSL`) are
  passed to the backend container from `infra/.env` and are **empty by default** —
  the channel then sends nothing, which is a valid state. A message is sent only
  when the credentials are set **and** an admin switched the channel on at
  `/admin/settings`. Put real credentials in `infra/.env` only (never in git or
  the database) and recreate the backend: `docker compose up -d backend`.
  The password-reset email (F2.3) uses the same email channel; its knobs are
  `PASSWORD_RESET_TTL_MINUTES` (30) and `PASSWORD_RESET_MAX_PER_HOUR` (3). To see
  reset emails locally, point `SMTP_*` at a mail catcher (e.g. Mailpit).
- The stack is for **development**; no TLS, default passwords, published ports.
