# Audit — F5.17 Admin coupons page is not route-split (2026-09-23)

## Task

`F5.17` (P3, Batch D), found during AB-FE-01. `routes/_authenticated/admin.coupons.tsx`
exported its page component (`export function AdminCoupons`). Nothing imports it, but
TanStack Router cannot split a route component that the route file also exports. The
dev server warned «These exports … will not be code-split», so the whole coupons page
sat in the shared entry chunk that every storefront visitor downloads. Part of the
"continue the whole backlog" run.

## Spec check (Rule 0)

No bundle rule in the spec. `[FE-07]` (the coupons manager) is unchanged in
behaviour. Nothing is in conflict.

## Recon

`grep` finds `AdminCoupons` only in its own route file (`component: AdminCoupons`).
Every other admin route is already a lazy `import()` in the entry.

## What was done

Dropped `export` from `function AdminCoupons()`. That is the whole code change.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/admin.coupons.tsx`
- docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`

## How to verify

**Production build:**

- Before: the page's strings (e.g. «کد جدید») are in `index-*.js` (410.80 kB).
- After: they are in a new `admin.coupons-*.js` (13.24 kB / 3.84 kB gzip).
- The entry is now 413.53 kB. The bundler re-split shared modules, which is why real
  page loads were measured below.

**Per-page JS transfer** (production build served from Node with gzip, as in F5.7):

| Page | Before (gzip) | After (gzip) |
| --- | ---: | ---: |
| `/` | 196.5 kB | **188.3 kB** (−8.2) |
| `/shop` | 204.5 kB | **196.2 kB** (−8.3) |
| `/about` | 182.9 kB | **174.7 kB** (−8.2) |
| `/admin/orders` | 228.0 kB | **222.4 kB** (−5.6) |
| `/admin/coupons` | 200.7 kB | 202.8 kB (+2.1; it loads its own chunk now) |

The "before" rebuild reproduced the original entry hash exactly (`index-DItb4zNc.js`).

**Regression** (dev stack): the coupon browser suites pass, F5.14 14/14, F5.16 15/15
and F5.9 14/14.

Gates:

- `prettier`, `tsc` clean;
- `bun run lint` 0 errors / 14 warnings (unchanged);
- `bun run build` OK.

**Verification level:** measured on the production build + browser tested.

## What is NOT done / open

- Nothing further. No other route file exports its component: the dev warning
  appears for no other route.
