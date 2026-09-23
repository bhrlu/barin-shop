# Audit — B6.8a Drop the redundant information_schema probe in `restore_stock()` (2026-09-23)

## Task

`B6.8a` (P3, Batch F). `order_lifecycle.restore_stock()` asked `information_schema`
on every cancellation whether `order_items.variant_id` exists. `startup_ddl()` always
creates that column (every backend boot and every seed job), so the probe was dead
weight. Required:

- select `variant_id` directly;
- keep the variant-then-aggregate order;
- keep the legacy NULL-`variant_id` behaviour.

Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

`[BE-05]` restock on cancellation is unchanged. Nothing is in conflict.

## Recon (Rules 6, 10)

- `CATALOG_DDL` has `ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS
  variant_id UUID …`, guarded but always ensured at boot (B6.16).
- The only reader of the probe was `restore_stock`, via `cancel_order_tx` (both
  cancel paths).
- B6.19's compare-and-set and AB-BE-01's ledger call sit on the same path and are
  unchanged.

## What was done

- `restore_stock` selects `product_id, variant_id, quantity` directly. A line with a
  `variant_id` restores that variant, then the aggregate. A NULL (legacy /
  matrix-less) line restores only the aggregate.
- The ledger's `return` row takes `item["variant_id"]` as is.

## Files changed

- `backend/app/services/order_lifecycle.py`
- `backend/tests/test_order_lifecycle_stock.py` (+1 test)
- docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/backend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`

## How to verify

- `pytest tests/test_order_lifecycle_stock.py`: 10 passed.
  - The existing tests cover variant + aggregate restore, a NULL-variant line and the
    B6.19 races.
  - The new test records every SQL statement a cancellation runs (a SQLAlchemy
    `before_cursor_execute` listener). It asserts that `order_items` is read and that
    `information_schema` is never queried.
- **Negative control:** with `HEAD`'s `order_lifecycle.py`, the new test fails.
- `tests/test_inventory_log.py` still passes (the ledger rows keep their variants).
- `pytest -q` **278 passed**; `ruff` clean.
- Smoke **252/0**, including «cancellation restores order stock (+1)».

**Verification level:** integration tested.

## What is NOT done / open

- Nothing.
