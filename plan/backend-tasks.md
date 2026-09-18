# Backend Task List (backend/)

Legend: `[ ]` todo · `[x]` done (audit file required) · audit links in `plan/audit/`

## Milestone B1 — Core service (Part 7, lean MVP)

- [x] **B1.1 Scaffold FastAPI project** — pyproject, app package, config, env example
  → audit: [2026-09-19-backend-scaffold.md](audit/2026-09-19-backend-scaffold.md)
- [x] **B1.2 DB layer** — async SQLAlchemy engine, models mirroring Supabase schema, coupon-table DDL
  → audit: [2026-09-19-backend-scaffold.md](audit/2026-09-19-backend-scaffold.md)
- [x] **B1.3 Supabase JWT auth + roles** — HS256 verify, aud=authenticated, admin/customer from user_roles
  → audit: same file as B1.1
- [x] **B1.4 Real coupon system** — coupons + coupon_redemptions tables, validate/create/list/update endpoints, usage caps, seed SANDE10 + WELCOME500
  → audit: same file as B1.1
- [x] **B1.5 Transactional stock decrement** — FOR UPDATE locks, guarded decrement, server-side prices
  → audit: same file as B1.1
- [x] **B1.6 Zarinpal payment gateway** — request/verify, callback with redirect, simulation mode, manual verify for polling clients
  → audit: same file as B1.1
- [x] **B1.7 Product search** — ILIKE search ranked name > category > description, pagination
  → audit: same file as B1.1
- [x] **B1.8 Tests + lint clean** — 19 unit tests, ruff clean, OpenAPI smoke test
  → audit: same file as B1.1
- [x] **B1.9 Backend became the sole service (no Supabase)** — own JWT auth
  (`security.py`/`auth.py`/`seed_auth.py`), real `public.users`, new routers
  (auth, products, orders, addresses, favorites, admin, storage), MinIO storage;
  40 operations across 34 paths. **Done unlogged** (see Session 3) — no tests for
  the new routers yet.
  → audit: [2026-09-19-sole-backend-no-supabase.md](audit/2026-09-19-sole-backend-no-supabase.md)

## Milestone B2 — Remaining Part-7 features (not started)

- [ ] **B2.1 SMS/email notifications** — Kavenegar/National SMS or SMTP on order placed/paid/shipped/cancelled/refund
- [ ] **B2.2 Reports & exports** — daily/monthly sales, best-sellers, Excel (openpyxl/pandas) + CSV product import/export
- [ ] **B2.3 PDF invoices** — reportlab/weasyprint, Persian digits, per-order invoice endpoint
- [ ] **B2.4 Recommendation engine** — related products from co-purchase patterns
- [ ] **B2.5 Webhooks + background jobs** — order events, abandoned-payment reminders, APScheduler
- [ ] **B2.6 Coupon admin UI support** — nothing to build in Python; expose whatever the admin panel needs (done as part of B1.4 API)
  → superseded by B1.9: `/admin/*` endpoints + `/coupons` CRUD now exist; the panel
  still needs wiring (frontend F1.2 / F2.4)

## Milestone B3 — Pay down debt from the sole-service rewrite

- [x] **B3.1 Fix `DATABASE_URL` examples** — `postgresql://` → `postgresql+asyncpg://`
  in `backend/.env.example`, `infra/.env.example`, `infra/docker-compose.yml`
  (startup failed with `ModuleNotFoundError: psycopg2`)
  → audit: [2026-09-19-sole-backend-no-supabase.md](audit/2026-09-19-sole-backend-no-supabase.md)
- [ ] **B3.2 Refresh `backend/README.md`** — remove the Supabase auth story, document the
  new routers, MinIO, and the bootstrap admin
- [ ] **B3.3 Refresh `infra/README.md`** — drop `01-auth-shim.sql` and "Supabase stays
  hosted"; document the sole-backend stack
- [ ] **B3.4 Clean stale Supabase wording in code** — `app/db.py` docstring/comments,
  `app/models.py` if applicable
- [x] **B3.6 Stack actually runs in Docker** — MinIO images moved to `quay.io`
  (Docker Hub publishing stopped Oct 2025), `minio-init` reuses the bundled `mc`,
  and the 7 runtime bugs it exposed are fixed (password hashing was fully broken;
  coupon seeding order; `auth.users` in the coupon DDL; `/search` param type;
  `/admin/stats` FILTER placement; MinIO presign int-vs-timedelta + host/region;
  payment callback always 404ing).
  → audit: [2026-09-19-docker-stack-up-and-runtime-fixes.md](audit/2026-09-19-docker-stack-up-and-runtime-fixes.md)
- [ ] **B3.7 Persist the payment authority** — a repeat Zarinpal callback returns
  400 instead of `already_paid`, because `reference` is overwritten with the
  `SND-…` code during verification. Needs an authority column (schema change
  decision) or an equivalent lookup path.
- [ ] **B3.5 Tests for the new routers** — auth (login/signup/me/roles), products CRUD +
  soft-delete, orders lifecycle, addresses, favorites, admin stats; needs a DB fixture
  (docker Postgres or testcontainers)

## Ideas (not scheduled)

- [ ] Redis cache for product catalog
- [ ] Rate limiting on checkout/payment endpoints
- [ ] Locale switch (i18n) for API error messages
