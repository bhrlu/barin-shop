# AB-BE-03 — Coupon max discount cap

**Date:** 2026-09-22
**Task ID:** `AB-BE-03` (P1 — Core product, `plan/MASTER-BACKLOG.md`; source
`plan/ADMIN-BACKEND_TASKS.md` `[BE-02]`)
**Title:** Coupon max discount cap

## Original requirement

A `percent_off` coupon had no ceiling, so a large cart could discount without
limit — direct revenue leakage. The backlog asks to:

* add `coupons.max_discount_cap`;
* expose it in schemas and admin CRUD;
* cap percentage discounts in the canonical pricing path;
* preserve fixed discounts;
* preserve min-order, usage and date rules;
* use the same calculation in coupon validation and checkout.

## Spec check (Rule 0)

* **`[BE-02]` Promotional Engine & Coupons** — *followed in intent, adapted in
  shape*. The spec lists `max_discount_cap (NUMERIC NULLABLE)` on a coupons table
  whose other columns it names `discount_type`/`value`/`min_order_amount`/
  `usage_limit`/`is_active`. The live table is `percent_off`/`amount_off`/
  `min_subtotal`/`max_uses`/`active` and every money column is `INTEGER` tomans,
  so the new column is `INTEGER` and sits beside the existing names. The live
  repo wins (Rule 0.2); renaming the other columns would be a breaking change no
  task asked for.
* **`[BE-06]` Coupon Validation Engine** — *followed*: validation and redemption
  run the same rules, which is exactly what the shared `compute_discount()` now
  guarantees for the cap too.
* **Spec stack header (Supabase RPC / RLS)** — *deliberately ignored*: the rules
  live in FastAPI services, not a `SECURITY DEFINER` function.
* **Rule 4 money rules** — untouched. Shipping stays ۸۹٬۰۰۰ with free delivery at
  ≥ ۲٬۰۰۰٬۰۰۰; the cap only limits a discount, and `quote()` is unchanged.

## Repository architecture check (Rule 6)

* **Owning module:** `backend/app/services/coupons.py` (`compute_discount`) for
  the rule, `backend/app/db.py` (`COUPON_DDL`) for the column,
  `backend/app/routers/coupons.py` + `app/schemas.py` for the contract.
* **Data flow:** cart → `src/lib/api.ts::validateCoupon` →
  `POST /coupons/validate` → `routers/coupons.py` → `services/coupons.py::
  validate_coupon` → `compute_discount`; checkout → `POST /checkout` →
  `services/checkout.py` → the *same* `validate_coupon` → `compute_discount` →
  `services/pricing.py::quote`. One function, two callers — which is why the cap
  went there and not into `pricing.py`.
* **Deviation from the prior audit:** `plan/audit/2026-09-22-full-backlog-audit.md`
  proposed clamping in `app/services/pricing.py`. `quote()` receives an already
  computed integer discount and knows nothing about coupons, so clamping there
  would have had to be duplicated for the validate endpoint — the exact
  "two sources of truth" Rule 7 forbids. The clamp is in `compute_discount()`
  instead, the single door both paths pass through.
* **API contract (Rule 8):** additive only. `CouponOut` gains
  `max_discount_cap: int | None = None` (defaulted, so every existing consumer
  keeps working); `CouponCreate` gains `max_discount_cap: int | None` (`gt=0`);
  `CouponUpdate` gains it with `ge=0`, where `0` clears the ceiling — the same
  "sentinel clears" convention `expires_at: ""` already uses on that schema; the
  admin list rows gain the field. No status code, error shape or pagination
  behaviour changed. `src/lib/api.ts` needs no edit to keep working (TypeScript
  ignores unknown extra response fields).
* **Auth (Rule 9):** unchanged. Creating/updating a coupon stays on
  `StaffCoupons`; `POST /coupons/validate` stays on `CurrentUser`. The cap is
  read from the database row only — a client cannot send a discount, a cap or a
  price. A customer calling `POST /coupons` with a cap gets 403 (tested, live and
  in pytest).
* **Money invariants (Rule 11):** the backend still computes the authoritative
  discount; the frontend only sends a code. Coupon-code normalisation
  (`strip().upper()`) is untouched and still identical in validation and
  redemption — verified live by validating with a lowercase code and checking out
  with the uppercase one.
* **Repeat safety (Rule 10):** the cap changes no state machine. Redemption
  still records one row per `(coupon_id, order_id)` and increments `used_count`
  once; the redemption row now stores the **capped** amount.

## Files changed

* `backend/app/db.py` — `COUPON_DDL` gains
  `ALTER TABLE public.coupons ADD COLUMN IF NOT EXISTS max_discount_cap INTEGER
  CHECK (max_discount_cap IS NULL OR max_discount_cap > 0)`.
* `backend/app/models.py` — `Coupon.max_discount_cap` (nullable Integer).
* `backend/app/services/coupons.py` — `compute_discount()` clamps a percent-off
  discount to the cap; `amount_off` untouched; docstring states why.
* `backend/app/schemas.py` — `CouponOut`, `CouponCreate`, `CouponUpdate`.
* `backend/app/routers/coupons.py` — validate + create responses return the cap,
  INSERT persists it, the admin list exposes it, PATCH sets/clears it, the
  create-audit entry records it.
* `backend/tests/test_pricing_and_coupons.py` — `make_coupon` gains the field;
  new `TestMaxDiscountCap` (9 cases).
* `backend/tests/test_coupon_cap_integration.py` — **new** DB-backed module
  (7 cases) proving validate and checkout agree and the admin CRUD round-trips.
* `backend/README.md` — coupon CRUD row, catalog-DDL list, and a note that
  `compute_discount` is the single computation point.

## Implementation summary

```python
if coupon.percent_off is not None:
    d = subtotal * coupon.percent_off // 100
    cap = getattr(coupon, "max_discount_cap", None)
    if cap is not None:
        d = min(d, int(cap))
elif coupon.amount_off is not None:
    d = coupon.amount_off
return max(0, min(d, subtotal))
```

The ceiling applies to percent-off coupons only: a fixed `amount_off` is already
a stated ceiling in tomans, and capping it again would silently shrink a discount
an admin typed. `NULL` means uncapped, so every coupon that existed before this
change — including the seeded `SANDE10` and `WELCOME500` — behaves exactly as
before. The `getattr` fallback keeps a stack whose DDL has not yet run from
raising. The existing `min(d, subtotal)` clamp still runs last, so a cap can
never push a discount above the cart.

## Tests executed

```
cd backend
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres \
  ./.venv/bin/python -m pytest -q tests/test_pricing_and_coupons.py        # 28 passed
DATABASE_URL=… ./.venv/bin/python -m pytest -q tests/test_coupon_cap_integration.py  # 7 passed
DATABASE_URL=… ./.venv/bin/python -m pytest -q                             # 70 passed
./.venv/bin/python -m ruff check app tests                                 # All checks passed
./.venv/bin/python tests/api_smoke.py                                      # 196 checks, 0 failed
```

Unit cases (`TestMaxDiscountCap`): percentage under the cap, over the cap,
exactly at it, without a cap, a fixed `amount_off` ignoring the cap, a cap larger
than the subtotal still clamped to the subtotal, `validate_coupon` applying the
same cap, and the cap **not** bypassing the `min_subtotal` or `max_uses` rules.

Integration cases: `POST /coupons/validate` returns the capped discount **and**
the cap; checkout records the identical amount in the returned quote, in
`orders.discount`, in `orders.total` and in `coupon_redemptions.amount`; a NULL
cap keeps the full percentage; a small cart under the ceiling is not clamped;
admin create → list → patch → clear (`0` → NULL) round-trips; a negative cap is
422; a customer creating a coupon is 403.

**Mutation check:** removing the three clamp lines turns exactly four tests red
(two unit, two integration) and leaves the other 66 green.

### Clean-environment verification (Rule 14)

```
cd infra && docker compose down -v && docker compose up -d --build
docker compose logs db-init     # exit 0, all four seed stages
docker compose ps               # postgres + minio + backend healthy
curl -fsS http://localhost:8000/health
psql \d public.coupons          # max_discount_cap integer + coupons_max_discount_cap_check
psql select … from coupons      # SANDE10 / WELCOME500 seeded with NULL cap
```

### Live runtime flow (fresh stack, real HTTP)

Admin created `CAPC0810` = 50% with a 300,000 cap; customer cart `set-19` × 3 =
5,670,000 (an uncapped 50% would be 2,835,000).

| call | result |
| --- | --- |
| `POST /coupons` (admin, cap 300000) | 201, response carries `max_discount_cap: 300000` |
| `POST /coupons/validate` with the code in **lowercase** | 200, `discount: 300000` |
| `POST /checkout` with the code | 200, `discount: 300000`, `total = 5,670,000 − 300,000 + 0` |
| validate vs. checkout | identical (asserted in the script) |
| `GET /coupons` (admin) | row shows cap 300000, `used_count: 1` |
| `PATCH /coupons/{id}` `{"max_discount_cap": 0}` | 200, list now shows `null` |
| re-validate as the same customer | 422 «شما قبلاً از این کد تخفیف استفاده کرده‌اید» (per-user limit still enforced) |
| `SANDE10` on the same cart | `discount: 567000`, `max_discount_cap: null` — seeded coupons unaffected |
| `WELCOME500` (fixed) | `discount: 50000` — fixed discounts preserved |
| `POST /coupons` with `max_discount_cap: -5` | 422 |
| `POST /coupons` as a customer | 403 |

Test coupon, test order and the product's stock were restored afterwards
(`set-19` back to its seeded 25).

## Verification level

**Fully verified** — unit + DB-backed integration tests, full suite, ruff,
`api_smoke.py` against the running stack, real-HTTP admin and customer flows, and
a `docker compose down -v` clean-environment proof of the DDL and the seeds.

## Remaining limitations

* **No admin UI field yet.** The cap is reachable only through the API; the F4.5
  coupon dialog (`admin.coupons.tsx`) and the `AdminCoupon` / create / update
  types in `src/lib/api.ts` do not mention it. AB-BE-03's layer is
  `backend_db_pricing` and the prior audit listed the dialog field as a
  *frontend dependency*, so it is recorded as a separate task rather than done
  here.
* **Fixed-amount coupons are deliberately uncapped.** If a future product
  decision wants the ceiling to apply to `amount_off` too, it is a one-line
  change in `compute_discount` plus tests — but it would silently shrink
  discounts admins stated explicitly, so it needs a decision.
* **No cap on the *stacked* effect of future promotions.** There is still exactly
  one coupon per order, so nothing stacks today.
* **`CouponUpdate` still cannot clear `max_uses` or `min_subtotal`** — the
  pre-existing `is not None` convention on that schema. The cap avoids the
  problem with its `0` sentinel; the others were left alone (Rule 12).

## Related follow-up findings

Recorded in the Master Backlog task index as discovered-during-AB-BE-03:

* `NEW-ABBE03-1` (P2) — expose `max_discount_cap` in the F4.5 admin coupon
  dialog and in the `AdminCoupon` / `adminCreateCoupon` / `adminUpdateCoupon`
  types in `src/lib/api.ts`, including the `0`-clears semantics.

No unrelated bug was fixed in this task.

## Docs deliberately left untouched

`infra/README.md`, `vogue-vintage-vibes/README.md`, `FEATURES.md`,
`DESIGN_SYSTEM.md` and `plan/README.md`: no infra step, UI, design token or
folder-index change. `plan/feature-roadmap.md` was left as is because the
capability is not yet user-visible — it becomes a feature line when
`NEW-ABBE03-1` ships the dialog field.
