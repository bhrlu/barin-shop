# Audit — F5.10 Hide staff nav tabs from non-staff (2026-09-23)

## Task

`F5.10` (P3, Batch D), found during F5.6. A signed-in customer on `/admin/*` saw the
«no admin access» notice, yet the sidebar still listed داشبورد / پیام‌ها / نظرات.
`admin.tsx` fell back to `ROLE_TAB_KEYS["support"]` for any role not in the map,
including `customer`. No data leaked, because every API call is capability-gated.
Required: no tabs for non-staff, with the staff mapping unchanged. Part of the
"continue the whole backlog" run.

## Spec check (Rule 0)

`[FE-01].3` auth guard: block non-admin users with a Persian permission error. The
notice already did that; the tabs contradicted it. Nothing is in conflict.

## Recon / security (Rules 6, 9)

- `useAuth().isAdmin` is true exactly for `admin`, `super_admin`, `order_manager` and
  `support` (`lib/auth.tsx`). It is also what gates the notice and the badge-KPI
  query.
- R9: hiding tabs is not authorisation, and nothing here relies on it. The backend
  already 403s every admin endpoint for customers.

## What was done

`admin.tsx`: `allowedKeys` is empty unless `isAdmin`. Staff keep `ROLE_TAB_KEYS[role]`,
and an unmapped staff role still degrades to the support trio. «بازگشت به فروشگاه»
stays for everyone.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx`
- docs:
  - `vogue-vintage-vibes/DESIGN_SYSTEM.md` (FE-01 row);
  - `vogue-vintage-vibes/FEATURES.md` (۴.۱.۱);
  - this audit;
  - `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/session-log.md`,
    `plan/README.md`.

## How to verify

Browser (Playwright), direct entry of `/admin/users`, desktop and the mobile sheet:
**11 checks, 0 failed**.

| Account | Tabs |
| --- | --- |
| customer | **0**, plus the no-access notice |
| support | 3 |
| order_manager | 7 |
| admin | 11 |

No page errors.

**Negative control** with `HEAD`'s `admin.tsx`: the customer sees
`["داشبورد","پیام‌ها","نظرات"]` on desktop and mobile (2 fail).

Gates:

- `prettier`, `tsc` clean;
- `bun run lint` 0 errors / 14 warnings (unchanged);
- `bun run build` OK.

**Verification level:** browser tested.

## What is NOT done / open

- The header's quick search and the storefront-preview link still show for a customer
  on `/admin`. They are harmless (they point at the storefront), and hiding them is
  not part of F5.10.
