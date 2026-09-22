# Audit — 2026-09-22 — Full end-to-end audit (backend + frontend) and fixes

## Task

Ad-hoc user request: perform a full end-to-end audit and test of the repository
— treat the implementation as unverified, run everything that can be run
(install, build, typecheck, lint, tests, Docker stack, live API, real browser),
try to break it, then fix what is actually broken. Not a task-list checkbox; new
follow-up checkboxes were added to `backend-tasks.md` / `frontend-tasks.md`.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before the work started.

**Followed**

- `[BE-05]` Order Lifecycle Management — its two explicit requirements ("validate
  state machine transitions, e.g. cancelled orders cannot move to shipped" and
  "restore stock on cancellation") were both missing from the implementation and
  are now implemented in `PATCH /orders/{id}` and `POST /orders/{id}/cancel`.
- `[BE-04]` RBAC — the audit confirmed roles live only in `user_roles`; the JWT
  `role` claim is no longer allowed to substitute for a missing staff role.
- `[FE-01]`.3 "Auth guard: block non-admin users, redirect with a Persian
  permission error" — the admin shell hid unauthorised tabs from the navigation
  but still rendered them on direct URL access; it now shows a Persian
  permission notice.
- Section B1.4 "All user-visible text in Persian" — the root 404 and error
  boundary were still the English Lovable scaffold copy; both are now Persian.
- Section B5 pre-flight checklist was used as the review lens for the admin and
  storefront routes (RTL, Persian copy, `formatPrice`, semantic tokens,
  skeleton/empty states, per-route `head()`).

**Deliberately not followed**

- The spec's stack header (Lovable Cloud / Supabase / `createServerFn`) — the
  live repo is FastAPI-only, per Rule 0.2. No change was made toward it.
- `[BE-07]` SMS gateway, `[BE-08]` CSV/XLSX export, `[FE-07]` coupons manager
  and `[FE-08]` role-change UI / LTV are still unimplemented. They are Part C
  backlog items, not regressions, and were left alone; they are recorded as new
  checkboxes instead.
- Status strings and the cart money rules (Rule 4) were not touched. The new
  state machine is expressed **in terms of** the existing
  `pending/processing/shipped/delivered/cancelled` vocabulary.

## What was done

### Environment brought up from scratch

`backend/.venv` created and `pip install -e ".[dev]"` run; `infra/.env` created
from the example (MinIO moved to ports 9010/9011 because 9000/9001 were already
taken on this host); `docker compose up -d --build` for the full five-service
stack; Playwright + headless Chromium installed for the browser passes.

### Bugs found and fixed

1. **P0 — `db-init` aborts, leaving a half-seeded database.** On a clean
   `docker compose up`, `python -m app.seed_auth` died with
   `invalid input value for enum app_role: "order_manager"`: the granular staff
   roles live in the *additive* startup DDL (`ROLE_DDL` in `app/db.py`), which
   only ran when the API container happened to boot first — and compose starts
   `db-init` and `backend` in parallel, with `db-init` depending on Postgres
   only. Because the seeds are chained with `&&`, products, demo orders and
   coupons never ran either. `seed_auth`, `seed_products` and `seed_demo` now
   call `startup_ddl()` first (as `seed_coupons` already did), so the job is
   self-sufficient. Verified from an empty volume (`down -v` → `up --build`):
   db-init exits 0 and seeds all four stages.

2. **P0 — `GET /products` returned 500 for every authenticated caller.**
   `_optional_admin` in `app/routers/products.py` built
   `AuthUser(uuid, email, role)` with the *string* from `resolve_role()`, while
   `AuthUser.roles` is a set, so `is_admin` raised
   `TypeError: unsupported operand type(s) for &: 'str' and 'set'` — a leftover
   from the B5.4 role refactor. Anonymous browsing worked, which hid it: the
   moment a shopper signed in, the catalog query (`catalogQuery`, used by the
   cart and the admin product list) failed, and the cart rendered every line as
   «محصول حذف‌شده» with a ۰ تومان total — i.e. no signed-in customer could
   check out. The duplicated dependency was deleted in favour of the already
   correct `app.auth.get_optional_user` (`OptionalUser`).

3. **P1 (security) — a customer could mark their own order paid.**
   `POST /orders/{id}/payment-complete` is the built-in payment *simulator*, but
   it was not gated on simulation mode: with a real Zarinpal merchant id
   configured it would still flip `payment_status` to `paid` on the client's
   word alone. It now returns 409 unless `simulation_mode()` is true (the
   previously private `_simulation_mode` was made public for this).

4. **P1 — settling a refund twice double-counted the money.** `PATCH
   /refunds/{id}` re-ran the whole settlement on an already-`refunded` request,
   inserting a second `refund` payment row for the same amount. An already
   settled request is now terminal (409), and the audit entry records the real
   previous status instead of a hardcoded `"pending"`.

5. **P2 — cancelled orders never returned their stock** (spec `[BE-05]`).
   Checkout decrements `products.stock`; neither the customer cancel nor an
   admin status change back to `cancelled` gave it back, so every cancellation
   permanently burned inventory. A `_restore_stock` helper now runs on the
   → `cancelled` transition only, so a repeated cancel cannot inflate stock.

6. **P2 — no order status state machine** (spec `[BE-05]`). `cancelled` →
   `shipped` was accepted. `_STATUS_TRANSITIONS` now allows only forward moves
   and treats `cancelled`/`delivered` as terminal (409 otherwise); re-setting
   the same status stays a no-op success.

7. **P2 — `GET /orders/{id}` 404'd for staff** although its docstring promised
   "owner or admin" and `_fetch_order` already supported it. Staff holding the
   `orders` capability can now read any order; everyone else stays scoped.

8. **P2 — coupon codes were case-insensitive at validation, case-sensitive at
   checkout.** `POST /coupons/validate` upper-cases and trims; the redemption
   lookup did not, so an API client that validated `sande10` successfully got
   "کد تخفیف معتبر نیست" at checkout. `get_coupon_for_update` now normalises
   identically. (The UI was unaffected — it stores the canonical code the
   validate call returns.)

9. **P2 — admin role gating was navigation-only.** An `order_manager` who typed
   `/admin/users` got the page plus a silent 403 and the "no users" empty state.
   The admin layout now maps the current path to its tab and renders a Persian
   permission notice when the role is not allowed.

10. **P3 (security hardening) — a stale JWT kept staff access.** `_resolve_roles`
    fell back to the token's `role` claim when the DB had no role rows, so a
    demoted admin stayed an admin until the (7-day) token expired. Only the
    harmless `customer` default is taken from the claim now.

11. **P3 (security hardening) — `POST /payments/verify` was not ownership
    scoped.** Any signed-in user could finalise a payment session by authority
    alone. `verify_and_finalize` takes an optional `user_id` (the gateway
    callback passes `None`, the authenticated route passes the caller) and
    reports a foreign session as unknown.

12. **P3 — the 404 and error-boundary pages were in English** ("Page not found",
    "This page didn't load", "Go home", "Try again") — leftover Lovable
    scaffold, contradicting spec B1.4. Translated.

13. **P3 — `/admin/users` labelled every non-`admin` role «مشتری»**, so the
    `support` and `order_manager` accounts displayed as customers. Replaced with
    a role-label map (unknown roles show their raw name).

14. **P3 — `bun run lint` failed** with 45 prettier errors. `bun run format` was
    run and the unrelated markdown/CSS reformatting it also produced was
    reverted, keeping the diff to the source files lint actually covers.

### Verified as *not* broken

Authorization matrix across anon/customer/support/order_manager/admin for all
`/admin/*` routes and `/coupons` (correct 401/403/200 throughout); signup mass
assignment (`"role": "admin"` in the body is ignored); JWT `alg=none` and
garbage tokens rejected; IDOR probes on orders, addresses, reviews, payment
sessions and refunds (all 404/403); checkout price injection (server-side prices
win); quantity bounds (1–20); cart money rules (۸۹٬۰۰۰ shipping, free ≥
۲٬۰۰۰٬۰۰۰); coupon min-subtotal, per-user cap and case handling; guest checkout
(shows a login link, never a dead submit); signup → account flow; the full
purchase flow through the simulated gateway to a paid order; the admin order
drawer, tracking code, invoice print, refunds, inbox, reviews and inventory
pages; responsive behaviour at 375/390/768/1024/1280/1440/1920 (no horizontal
overflow on any audited page) and the mobile admin sheet.

## Files changed

- `backend/app/seed_auth.py`, `backend/app/seed_products.py`,
  `backend/app/seed_demo.py` — run `startup_ddl()` before seeding.
- `backend/app/routers/products.py` — drop the broken `_optional_admin`
  duplicate, use `OptionalUser`.
- `backend/app/routers/orders.py` — status state machine, stock restoration,
  staff single-order read, terminal refund settlement, simulation-mode gate.
- `backend/app/routers/payments.py`, `backend/app/services/payments.py` —
  ownership-scoped manual verify; `simulation_mode()` made public.
- `backend/app/services/coupons.py` — normalise the redemption lookup.
- `backend/app/auth.py` — no staff role from a stale token claim.
- `vogue-vintage-vibes/src/routes/__root.tsx` — Persian 404 / error pages.
- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx` — per-route role
  guard.
- `vogue-vintage-vibes/src/routes/_authenticated/admin.users.tsx` — staff role
  labels.
- Prettier formatting only: `src/lib/api.ts`, `src/lib/auth.tsx`,
  `src/lib/cart.tsx`, `src/data/products.ts`,
  `src/components/admin/OrderDetailDrawer.tsx`,
  `src/routes/_authenticated/{account.favorites,admin.index,admin.messages,admin.orders,admin.refunds}.tsx`,
  `src/routes/{about,index}.tsx`.
- Docs: this audit, `plan/backend-tasks.md`, `plan/frontend-tasks.md`,
  `plan/session-log.md`, `plan/feature-roadmap.md`.

## How to verify

```bash
# clean stack from an empty volume — db-init must exit 0 and seed all four stages
cp infra/.env.example infra/.env   # set JWT_SECRET; free ports for MinIO if needed
cd infra && docker compose down -v && docker compose up -d --build
docker compose logs db-init        # expect 4 users, 20 products, 2 orders, 2 coupons

# backend
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests             # clean
./.venv/bin/python tests/api_smoke.py                  # 173 checks, 0 failed

# frontend (inside the container, or with bun locally)
docker compose exec frontend sh -c "cd /app && bunx tsc --noEmit"   # clean
docker compose exec frontend sh -c "cd /app && bun run lint"        # 0 errors
docker compose exec frontend sh -c "cd /app && bun run build"       # succeeds
```

Manual spot checks: sign in as `customer@sande.local` and confirm the cart shows
the real product and total (regression for bug 2); cancel an order and confirm
`GET /products/{id}` stock goes back up; `PATCH /orders/{id}` from `cancelled`
to `shipped` returns 409; sign in as `support@sande.local` and open
`/admin/orders` — expect the Persian permission notice; visit `/nope` for the
Persian 404.

## What is NOT done / open

- **`order_items` has no `variant_id`**, so cancellation restores the
  product-level aggregate only; per-variant stock stays decremented. Recorded as
  a new backend checkbox.
- **Refund request creation swallows every exception** into a 409 "already
  requested" (`except Exception` around the INSERT), which would mask a real DB
  error. Left as-is to avoid changing an existing contract mid-audit; recorded
  as a checkbox.
- **Unimplemented spec features** (`[FE-07]` coupons manager, `[FE-08]` role
  change + LTV, `[BE-07]` SMS, `[BE-08]` exports, `[FE-02]` reusable data grid,
  an audit-log UI for the shipped `/admin/audit-logs` endpoint) — backlog, not
  regressions.
- **Performance, reported but not changed:** `/shop` fetches the catalog twice
  per visit (`/products?include_inactive=true` and `/products?sort=new`); the
  client bundle ships recharts (~553 kB raw) and lodash (~164 kB) for the admin
  dashboard charts with no route-level split; `/products` and `/admin/orders`
  have no pagination and return the whole table.
- **Not testable here:** the real Zarinpal gateway (simulation mode only), SMTP
  /SMS (none configured), and any production TLS/reverse-proxy behaviour.
- `plan/feature-roadmap.md` had two claims the audit disproved and both were
  corrected: "Sign-up/login with email and **Google**" (no Google provider exists
  anywhere in the repo — a Supabase-era leftover) and "the admin inbox screen is
  still missing", which shipped as `/admin/messages`.
- `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
  `FEATURES.md` and `DESIGN_SYSTEM.md` were **deliberately left untouched**: no
  endpoint, setup step, script, feature or design token changed — every fix
  restored documented behaviour rather than altering it. `plan/README.md` is
  still accurate (it indexes the folder, not individual audits).
