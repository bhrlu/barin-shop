# Audit — B6.15 `POST /coupons` accepts both discount kinds or neither (2026-09-23)

## Task

`B6.15` (P3, Batch C), found during F5.16. `CouponCreate._not_both` was a no-op
validator, so `POST /coupons` could store a coupon in two broken ways:

- with **both** `percent_off` and `amount_off`, where `compute_discount` prefers the
  percent and silently ignores the amount;
- with **neither**, which gives a discount of 0.

The admin dialog has blocked both cases since F5.16, but direct API callers were not
blocked. Required: exactly one kind on create, a 422 in Persian with the same wording
as PATCH, and an unchanged payload shape. First P3 task of the "continue the whole
backlog" run.

## Spec check (Rule 0)

`[BE-02]` coupons: a percentage **or** a fixed amount. No conflict. The stack header
is ignored.

## Recon / contract (Rules 6–9)

- **Owner:** `routers/coupons.py::create_coupon` (`StaffCoupons`). The PATCH rule and
  its message live in the same router: «کد تخفیف یا درصدی است یا مبلغ ثابت؛ فقط یکی
  را بفرستید».
- **Other creators:**
  - the frontend `adminCreateCoupon` sends exactly one kind (F5.16);
  - the seeds insert with SQL, one kind each;
  - the tests always send one.
- **Contract:** request and response unchanged. New 422s for both and for neither.

## What was done

- `create_coupon` rejects both kinds (the PATCH message) and neither («درصد تخفیف یا
  مبلغ ثابت را بفرستید؛ کد بدون تخفیف معنا ندارد») before anything is written.
- The misleading no-op `_not_both` validator was removed from `CouponCreate`.
- Tests: +4 in `tests/test_coupon_update.py` (both / neither → 422 with nothing
  stored; percent only and amount only → created). Smoke +1 check.

## Files changed

- `backend/app/routers/coupons.py`, `backend/app/schemas.py`
- `backend/tests/test_coupon_update.py`, `backend/tests/api_smoke.py`
- docs: `backend/README.md` (coupons row), this audit, `plan/MASTER-BACKLOG.md`,
  `plan/backend-tasks.md`, `plan/session-log.md`, `plan/README.md`

## How to verify

- `pytest tests/test_coupon_update.py`: 11 passed. **Negative control** with `HEAD`'s
  router: the two new 422 tests fail.
- `pytest -q` 271 passed; `ruff` clean.
- Smoke **247/0**, including «POST /coupons with both discount kinds → 422».

**Verification level:** integration tested.

## What is NOT done / open

- Coupons already stored with both kinds or neither (possible before this fix, API
  only) are not migrated. The seeds never create them, and PATCH (F5.16) fixes one
  when it is edited.
- Frontend: untouched (the dialog already enforces one kind).
