# Audit — 2026-09-22 — B2.4 co-purchase recommendation engine

## Task

**B2.4** from `plan/backend-tasks.md`: "Recommendation engine — related
products from co-purchase patterns."

## Spec check (Rule 0)

The dev spec has no recommendation section (its Part C stops at search/KPIs);
the task wording in the repo list is the requirement. [BE-08]-style REST
adaptation not needed — the existing `/products/{id}/recommendations`
contract is unchanged, so the frontend (F3 rails) needs **zero changes**.
No Rule-4 statuses or money rules touched.

## What was done

**New `app/services/recommendations.py`**
- `CO_PURCHASE_DDL` — `co_purchases(product_a, product_b, votes)` with a
  `CHECK (product_a < product_b)` canonical pair ordering; created idempotently
  in `startup_ddl` (via a small local import in `db.py` to avoid a circular
  import: routers → services → db).
- `refresh_co_purchases()` — recomputes all pairs from `order_items`:
  every multi-item order contributes `COUNT(DISTINCT order_id)` votes to each
  unordered pair (`LEAST/GREATEST` keeps pairs canonical). Runs in the
  **checkout transaction** (only when the cart has ≥2 lines) so the engine
  learns immediately, and once at startup for fresh stacks.
- `CO_VOTES_SQL` — scalar-subquery fragment counting shared-pair votes.

**`/products/{id}/recommendations` now blends** (same payload shape):
co-purchase votes ×3 + same-category +100 + published-review count ×2 +
`is_new` +10 + base 5, ties broken by `created_at`. The heuristic keeps the
old "same category first" promise and covers never-bought-together products,
so the endpoint is **never worse than pre-B2.4**. `/related` (pure same-category)
is untouched.

**Verification catches (both real bugs):**
1. First version referenced `p.review_count` as a column — it's a correlated
   subquery alias in `_PRODUCT_COLS`, not a column → 500. Fixed by composing
   the recommend query from `_PRODUCT_COLS` + the score expression, keeping
   the subquery duplicated deliberately (single source of truth stays the
   columns constant).
2. First version appended a second `FROM` after `_SELECT` (which already
   contains one) — `syntax error at "*"`. Symptom of the same fix.

## Files changed

- `backend/app/services/recommendations.py` (new)
- `backend/app/db.py` (co_purchases DDL + startup refresh)
- `backend/app/routers/products.py` (blended ranking)
- `backend/app/services/checkout.py` (in-transaction refresh, multi-item carts)
- `backend/tests/api_smoke.py` (first cart is now 2 lines; self-exclusion/cap
  check; post-checkout health check)

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests             # clean
./.venv/bin/python tests/api_smoke.py                  # 189 checks, 0 failed
docker exec sandeh-postgres-1 psql -U sande -d postgres \
  -c "SELECT * FROM co_purchases ORDER BY votes DESC"  # pairs learned
```

Live after the smoke run: `set-18 | tshirt-4 | votes=2` (repeat runs),
`set-17 | tshirt-4 | 1`; `/products/set-18/recommendations` returns
`set-17` (a co-purchased set) ahead of same-category peers.

## What is NOT done / open

- **No cold-start item metadata engine** — recommendations are popularity-
  heuristic until real multi-item orders accumulate; acceptable for the
  catalog size, revisit if conversion data is wanted sooner.
- votes are order-count based (not revenue/quantity weighted); quantity
  weighting is a one-line change if desired.
- The pair table grows O(products²) in theory; at this catalog scale the
  full refresh stays well under a second. No TTL/partitioning needed.
- Docs touched: this audit, B2.4 tick, session log 29c, backend README,
  roadmap §1 note, plan README.
