# Audit — F5.9 Coupon discount-cap field in the admin dialog (2026-09-23)

## Task

`F5.9` (P2, Batch B — its last open item). AB-BE-03 added `coupons.max_discount_cap`
(a toman ceiling on percent-off discounts) to the API; the F4.5 dialog could not set
it. First task of the "whole backlog" run.

## Spec check (Rule 0)

`[FE-07]` coupon manager / `[BE-02]` cap — followed. Colours via existing tokens
(disabled input uses `disabled:opacity-50`); Persian copy and digits.

## Recon / contract (Rules 6, 8)

`src/lib/api.ts` (`AdminCoupon`, `adminCreateCoupon`, `adminUpdateCoupon`) →
`POST/PATCH /coupons` (`max_discount_cap`: `null` = uncapped on create, `0` clears on
PATCH — AB-BE-03) → `services/coupons.compute_discount` (the only place the cap is
applied, percent coupons only). `admin.coupons.tsx` kept its own copy of the
`AdminCoupon` type — replaced by the canonical import (R7) instead of adding the field
twice. No backend change.

## What was done

- `api.ts`: `max_discount_cap` on `AdminCoupon`, the create input and the PATCH type.
- Dialog: «سقف تخفیف درصدی (تومان)» input, enabled only while «درصد تخفیف» is filled
  (placeholder «فقط برای کد درصدی» otherwise); create sends the value or `null`; edit of
  a percent coupon sends the value or `0` (clears); an amount coupon never sends it.
- Card: «۲۰٪ تخفیف، حداکثر ۱۰۰,۰۰۰ تومان» when capped.

## Files changed

`vogue-vintage-vibes/src/lib/api.ts`,
`vogue-vintage-vibes/src/routes/_authenticated/admin.coupons.tsx`; docs: this audit,
`plan/frontend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`.

## Verification results

| Check | Result |
|---|---|
| Headless Chromium, `/admin/coupons` | **14/14** — create 20 % capped at 100 000 → persisted, **`/coupons/validate` on 1 000 000 → 100 000**, card shows the ceiling; edit pre-fills it; raise to 150 000 → 150 000; clear → `null` and the full 200 000; field disabled for a fixed-amount coupon, which is created uncapped; mobile 390 px dialog fits; no page errors |
| Regression: F5.16 / F5.14 coupon suites | 15/15 / 14/14 |
| prettier / `tsc` / lint / build | clean / clean / 0 errors (15 pre-existing warnings) / OK |

**Verification level: browser tested** (frontend-only; the discount itself was checked
through the backend's validate endpoint).

## What is NOT done / open

- A percent coupon switched to a fixed amount keeps its stored cap (ignored for amount
  coupons by `compute_discount`); B6.15 (create-time kind validation) still open.
