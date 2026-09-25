# 2026-09-25 — AB-FE-06 Customer 360° profile (D7b tiers)

## Task

`plan/MASTER-BACKLOG.md` §AB-FE-06 (Batch F, P3, full-stack): customer
overview, registration date, order history, saved addresses, wishlist, LTV,
average days between purchases, role-management entry point, customer tier —
per spec [FE-08] on the admin users surface. D7(b) semantics are binding:
New < 3 delivered ≤ VIP; Wholesale staff-assigned and taking precedence;
**role ≠ tier**; the task may add the smallest canonical tier representation.

## Spec check (Rule 0)

[FE-08] Customer 360° Profile & CRM read in full (the spec's only section for
this task): avatar with initials, tier badge (جدید/وفادار/همکار), registration
date, three tabs (تاریخچه سفارشات · آدرس‌های ثبت‌شده · علاقه‌مندی‌ها), LTV +
average-days cards, role-change trigger with a two-step confirmation. Live-repo
precedence applied (Rule 0.2): the two-step role dialog **already exists** in
`admin.users.tsx` (F5.6/B5.4), so [FE-08]'s "role change trigger" is satisfied
by an entry point into it — no second role UI was built. B4.1's
`formatPrice`/`toPersianDigits` are this repo's `formatToman`/`toFa`; B4.2's raw
palette classes are the token-driven `StatusBadge` (F4.1). No spec edited.

## What was done

**Backend**

1. `public.user_tiers` (idempotent `USER_TIER_DDL` in `app/db.py`): the
   smallest canonical explicit-tier representation — `user_id PK`,
   `tier TEXT CHECK (tier IN ('wholesale'))`, `updated_by`, `updated_at`.
   Deliberately **not** in `user_roles` (role ≠ tier, D7b) and not a column on
   `profiles` (tier is classification, not identity).
2. `app/services/tiers.py` — the one canonical implementation (R7):
   `resolve_tier(delivered, explicit)` is the pure D7b rule (unknown explicit
   values ignored, so a bogus row cannot fake a tier); `resolve_tier_for_user`,
   `get_explicit_tier`, `set_explicit_tier` (caller audits + commits).
   `VIP_DELIVERED_ORDERS = 3` lives only here.
3. `GET /admin/users/{user_id}/profile` (StaffUsers guard): identity + roles,
   tier, stats (order_count, delivered_count, **LTV** = Σ total of
   non-cancelled orders, favorite_count, address_count,
   **avg_days_between_purchases** from delivered-order timestamps, ≥2
   required), plus full orders (the shared `_ORDER_SELECT` shape, items
   included), addresses and favorites — each read from the customer's own
   sources; no second copy of account data (R7). 404 unknown user.
4. `PUT /admin/users/{user_id}/tier` (StaffUsers): assigns/clears the explicit
   Wholesale flag; only `wholesale` is staff-assignable (anything else 422);
   audited as `update_user_tier` with old/new explicit tier; returns the
   effective tier. Same guard family as `PUT /users/{id}/roles`.
5. `GET /admin/users` rows now carry `delivered_count`, `explicit_tier` and
   the resolved `tier`, so the list can badge every customer.

**Frontend**

6. `src/lib/api.ts`: `CustomerTier`, `AdminCustomerProfile` types;
   `AdminUser` extended (`delivered_count`, `explicit_tier`, `tier`);
   `api.adminCustomerProfile()` + `api.adminSetUserTier()`.
7. `src/lib/tiers.ts`: shared Persian tier labels (display copy only —
   semantics stay server-side).
8. `src/components/admin/CustomerProfileDrawer.tsx` (new): Sheet drawer per
   [FE-08] — initials avatar, tier badge, registration date; LTV and
   avg-days-between-purchases cards; orders / addresses / favorites tabs with
   loading, error and empty states; the Wholesale assign/clear flow with a
   typed confirmation step; a «مدیریت نقش‌ها» button that closes the drawer
   and opens the existing two-step `RolesDialog` (one role UI, two-step
   confirmation preserved).
9. `admin.users.tsx`: «سطح» column with the tier badge; «پروفایل» row action
   opening the drawer; drawer mounts beside `RolesDialog` and can hand off to
   it.

## Decisions

- **LTV excludes cancelled orders** (`status <> 'cancelled'`) to match the
  existing `GET /admin/users` `spent` convention; the order **history** keeps
  all orders including cancellations (a valid cancellation is part of the
  360° view). Recorded here so the two numbers are never "reconciled" by
  accident.
- **Average days between purchases is computed from delivered orders only**
  (≥2 needed, else `null`) — the D7b cadence is about completed purchases.
- **Tier labels are UI copy in `lib/tiers.ts`**; the rule and threshold stay
  in `services/tiers.py`, so client and server cannot drift on semantics.
- **Only `wholesale` is assignable** — New/VIP are derived states; making them
  settable would create a second source of truth that silently diverges from
  the delivered-order count.
- **Wholesale lives in its own table**, not `user_roles`: a Wholesale customer
  gains no staff capability and a staff member is not thereby Wholesale.

## Tests

* `tests/test_customer_profile_tier.py` (new, 19 tests): pure tier math
  (thresholds, wholesale precedence, unknown explicit ignored, role≠tier);
  endpoint integration — overview matches the customer's own sources (LTV
  excludes the cancelled 50k while the history keeps all 3 orders), tier flips
  new→vip exactly at 3 delivered, wholesale flag wins over the count,
  avg-days = 6.0 for a 10→4 day pair, 404/401/403 guards (support role refused
  — `users` capability is admin/super_admin only), set+clear via the endpoint
  with the `update_user_tier` audit row asserted, wholesale grants no staff
  access, bogus tier 422, list rows carry the tier. Throwaway rows removed in
  teardown.
* `tests/api_smoke.py`: +9 checks — tier present on a users-list row, the
  360° view shape, anonymous 401, customer 403 on their own profile.

## Verification

* `ruff check app tests` — clean; `python -c "app.openapi()"` — 74 paths
  (was 72; the two new admin routes registered).
* `pytest -q` — **396 passed** (was 377; +19). One spurious fixture ERROR in
  the first full-suite run did not reproduce and `test_profile.py` passes
  57/57 standalone — recorded as a one-off flake, not masked.
* Live stack: smoke **266 checks, 0 failed** (was 257).
* Live acceptance probe (throwaway signup, removed after): `PUT tier` →
  `wholesale`; list row and profile both report `wholesale`; clear → `new`.
  The probe's audit rows remain by design (append-only; actor/target rows are
  gone, `ON DELETE SET NULL` keeps the trail). 0 probe users / 0 tier rows
  left in the DB.
* Frontend: `tsc --noEmit` 0 errors; eslint clean on all touched files;
  `npm run build` green (Node 22 via nvm — the known Node 20.9 limitation).

## What is NOT done / open

* **Browser click-through of the drawer** — no browser automation exists
  (decision D10 gate); verified at API/runtime level + build. Left OPEN.
* Wishlist tab shows product ids (the favorites source has no product join in
  the profile payload); titles/images would need a products join — follow-up
  if the drawer needs merchandising context.
* No pagination inside the drawer's orders tab (a heavy buyer loads all their
  orders; acceptable for now, flagged for the F2.5 admin-pagination task).
* Tier has no effect on pricing or capabilities anywhere (D7b: classification
  only); a future Wholesale price list is a separate decision.
* F5.20's richer self-service profile (national ID, size profile) stays
  separate — AB-FE-06 is the staff-facing view and did not merge them.

## Docs synced

`MASTER-BACKLOG.md` (§AB-FE-06 DONE section, JSON entry, NEXT → F3.2c, counts
53 DONE / 6 TODO of 59, dependency trees), `frontend-tasks.md` (AB-FE-06
checkbox), `session-log.md`, this audit.
