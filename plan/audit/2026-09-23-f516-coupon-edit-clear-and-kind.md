# Audit — F5.16 Coupon edit dialog could not clear fields or switch kind (2026-09-23)

## Task

`F5.16` (P2, Batch D), discovered during F5.14: the `/admin/coupons` edit dialog
sent `null` for an emptied field and `PATCH /coupons/{id}` treats `null` as
"unchanged", so clearing the expiry or the total cap did nothing. Second task of
the user's "B6.14 then F5.16" run.

**It was also a pricing bug (R11).** Switching a 10 % coupon to a fixed 50 000
stored *both* values; `services/coupons.py::compute_discount` prefers
`percent_off`, so customers kept getting 10 % — the admin's change was silently
ignored at checkout.

## Spec check (Rule 0)

`[FE-07]` coupon manager and `[BE-02]` / `[BE-06]` (one authoritative discount) —
followed. `F5.9` (the discount-cap field in the dialog) is separate and untouched.

## Contract (Rule 8) — `PATCH /coupons/{id}`, backward-compatible

- omitted / `null` → unchanged (every existing caller keeps working);
- `expires_at: ""` → no expiry (already supported by the backend; the dialog now
  sends it);
- `max_uses: 0` → unlimited (NULL) — new, mirrors the `max_discount_cap: 0`
  convention; negative → 422 (was: `0` → 422);
- setting `percent_off` clears `amount_off` and vice versa — a coupon always has
  exactly one kind; both in one request → **422**
  «کد تخفیف یا درصدی است یا مبلغ ثابت؛ فقط یکی را بفرستید», nothing changed.

Auth unchanged (`StaffCoupons`); the change is audited as before with old → new
values (both kind columns appear on a switch).

## What was done

- `schemas.CouponUpdate`: `max_uses` `ge=0`; docstring states the clear rules.
- `routers/coupons.py::update_coupon`: kind switch clears the other kind, both →
  422, `max_uses: 0` → NULL.
- `admin.coupons.tsx` save: validates "exactly one of percent / amount" (new
  Persian error when both are filled); on **edit** sends only the chosen kind,
  `expires_at: ""` when emptied and `max_uses: 0` when emptied; **create**
  payload unchanged (nulls). `api.ts` documents the PATCH encodings.

## Files changed

`backend/app/schemas.py`, `backend/app/routers/coupons.py`,
`backend/tests/test_coupon_update.py` (new), `backend/README.md`;
`vogue-vintage-vibes/src/routes/_authenticated/admin.coupons.tsx`,
`vogue-vintage-vibes/src/lib/api.ts`; docs: this audit, `plan/frontend-tasks.md`,
`plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q tests/test_coupon_update.py   # 7 passed
```

Browser: `/admin/coupons` → «ویرایش» on a 10 % coupon → empty «درصد تخفیف», fill
«مبلغ ثابت» 50000 → save → `POST /coupons/validate` on 1 000 000 returns 50 000.

## Verification results

| Check | Result |
|---|---|
| `tests/test_coupon_update.py` (money path through `/coupons/validate`) | **7 passed** — `""` clears expiry; `max_uses: 0` → unlimited, `-1` → 422; 10 % → fixed 50 000 changes the real discount 100 000 → 50 000; fixed → 20 % clears the amount (200 000); both kinds → 422 and nothing changes; null fields unchanged; the switch is audited with both kind columns old → new |
| **Negative control** (previous router + schema) | 5 failed, 2 passed (the passing two: `""` expiry, already supported server-side, and the null-unchanged compatibility check) |
| full `pytest -q` | **170 passed** (163 + 7) on 9 consecutive runs. One earlier run — the first after the negative-control file swaps — reported 1 error; its text was not captured (my command kept only the summary line) and it did not reproduce in the 9 runs, 3 of them with backend hot-reloads forced mid-run. Recorded as unexplained, not as a pass. **Update (B5.4b, same day):** the same symptom was reproduced and traced to `startup_ddl()` deadlocking with in-flight queries when the dev container hot-reloads (see B6.16) — the most likely cause of this one too. |
| `ruff` / `api_smoke.py` | clean / **229 checks, 0 failed** |
| Headless Chromium, `/admin/coupons` dialog | **15/15** — create unchanged; clear expiry → persisted + «بدون محدودیت»; clear total cap → unlimited + «نامحدود»; both kinds filled → Persian client error and **no request**; 10 % → 50 000 persisted, real discount 50 000, request carried only `amount_off` + `expires_at: ""` + `max_uses: 0`; back to 20 % → 200 000; delete; no page errors |
| Regression: F5.14 coupon suite | **14/14**; its observation now reads `expires_at=null` after clearing (was the old date) |
| prettier / `tsc` / lint / build | clean / clean / 0 errors (15 pre-existing warnings) / OK |

No schema change (validation + UPDATE logic only), so no clean-environment run.
**Verification level: integration tested + browser tested.**

## Discovered (recorded, not fixed)

- **B6.15** (`NEW-F516-1`, P3) — `POST /coupons` accepts both kinds or neither:
  `CouponCreate._not_both` is a no-op stub. The dialog now blocks it; the API does
  not. Validate exactly one kind on create (422).

## What is NOT done / open

- B6.15 above; F5.9 (discount-cap field) still open — `max_discount_cap` stays
  untouched by a kind switch (it only applies to percent coupons).
- `min_subtotal` / `max_uses_per_user` have no "clear" state by design (0 and 1 are
  real values the dialog already sends).
