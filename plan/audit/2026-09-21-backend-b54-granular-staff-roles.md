# Audit — 2026-09-21 — B5.4 granular staff roles (spec [BE-04])

## Task

**B5.4** from `plan/backend-tasks.md`: granular staff roles
(`super_admin` / `order_manager` / `support`) alongside the existing binary
`admin` / `customer`, enforced per route. Spec **[BE-04]**: roles live in
`user_roles` (never on the user row), admin `has_role` unrestricted.

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` §[BE-04] before starting.

- **Followed:** the three staff roles + the `user_roles` table contract
  (`UNIQUE(user_id, role)`, roles never on `profiles`/users); capability
  enforcement happens per route from the DB-backed role set.
- **Adapted:** the spec defines no capability matrix (role names only) — the
  matrix is ours, mapped from role semantics and documented in
  `app/services/roles.py`. RLS/`has_role` SQL policies are replaced by FastAPI
  guards (this repo's standing adaptation — the backend is the sole authority).
- **Spec-stack staleness (known):** spec still says Supabase/auth.users; live
  repo is FastAPI + `public.users`. Conflict reported here, per the working
  agreement.

## What was done

**Role model**
- `ROLE_DDL` (idempotent, autocommit): extends `public.app_role` enum with
  `super_admin`, `order_manager`, `support`. Legacy `admin` rows keep working —
  treated as a full staff role everywhere (Rule 4: existing rows never break).
- `app/services/roles.py::ROLE_CAPABILITIES` — the closed capability map:
  - `orders` / `refunds` → admin, super_admin, order_manager
  - `contact_inbox` / `stats` → all staff
  - `catalog` / `coupons` → admin, super_admin, order_manager
  - `reviews` → admin, super_admin, support
  - `users` / `audit` → admin, super_admin only
- `app/auth.py`: `AuthUser.roles` (full set), `require_staff(capability)`
  dependency factory + `Staff*` aliases; `resolve_roles` reads `user_roles`.
  `require_admin` docstring corrected (any staff passes; it is legacy).

**Per-route enforcement** — routers switched from `AdminUser` to capability
guards: orders.py (`StaffOrders`/`StaffRefunds`), admin.py (`StaffStats`,
`StaffUsers`, `StaffAudit`, `StaffOrders`, `StaffRefunds`), contact.py
(`StaffContactInbox`), coupons.py, products.py (`StaffCatalog`), reviews.py
(`StaffReviews`). storage.py keeps the coarse `AdminUser` (upload surface).

**Role administration (needed to make the roles usable)**
- `PUT /admin/users/{id}/roles` — PUT semantics (full replacement of the
  `super_admin`/`order_manager`/`support` set), admin/super_admin-only, 404 on
  unknown user, audited via `update_user_roles` (new action) with old/new role
  sets — closes the "role changes not auditable until B5.4" note from B5.1.
- `app/seed_auth.py`: demo staff accounts `ordermgr@sande.local` /
  `support@sande.local` (password `staff1234`).

**Frontend (minimal, unblocking)**
- `src/lib/auth.tsx`: the admin-shell gate now accepts all staff roles
  (`user.role` is the display role from `/auth/me`, which resolves the
  highest-privilege role via `resolve_role`). Per-tab UI gating is **F4.2** and
  remains open — a `support` account currently sees all tabs; the API still
  rejects calls it may not make (403s), so this is UX-only exposure.

## Files changed

- `backend/app/db.py` — `ROLE_DDL` + autocommit wiring
- `backend/app/services/roles.py` — capability map + role resolution
- `backend/app/auth.py` — role set on `AuthUser`, `require_staff`, aliases
- `backend/app/routers/{admin,orders,contact,coupons,products,reviews}.py` — per-route guards; roles endpoint in admin.py
- `backend/app/services/audit.py` — `update_user_roles` action, `user` entity
- `backend/app/seed_auth.py` — demo staff accounts
- `backend/tests/api_smoke.py` — B5.4 flow (12 checks)
- `vogue-vintage-vibes/src/lib/auth.tsx` — staff-role shell gate

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
cd backend && ./.venv/bin/python -m ruff check app tests
cd backend && ./.venv/bin/python tests/api_smoke.py    # 156 checks, 0 failed
docker exec sandeh-backend-1 python -m app.seed_auth   # seeds demo staff
```

Live smoke exercises the full flow: customer cannot self-grant (403) → admin
grants `order_manager` → that user reads orders/KPIs, is blocked from audit
log/users/review-moderation (403s), saves a tracking code → `support` is
blocked from `/admin/orders` but reaches the contact inbox → role change
visible in the audit log with old/new values → demote to `[]` → staff access
gone (403). Throwaway user, DB left as it started.

## What is NOT done / open

- **F4.2 per-tab admin gating** — the shell shows every tab to every staff
  role; only the API enforces the matrix today (403s surface as errors).
- **`super_admin` has no unique power yet** — same as `admin` everywhere. It
  exists so B5.1b/`users`-capability tightening has a top role to tier into.
- **Roles endpoint is PUT-only** — no role *list* endpoint (the users list
  already carries each user's roles).
- Docs deliberately untouched: `plan/ADMIN-*.md` (static spec copies),
  `vogue-vintage-vibes/DESIGN_SYSTEM.md` / `FEATURES.md` (no UI/design change —
  the auth.tsx gate is logic, not componentry).
