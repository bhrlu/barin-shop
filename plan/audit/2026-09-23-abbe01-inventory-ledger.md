# Audit — AB-BE-01 Inventory ledger (2026-09-23)

## Task

`AB-BE-01` (P2, Batch C; depends on B6.8, which is done). Create `inventory_logs`
(`id`, `variant_id`, `change_amount`, `reason`, `created_by`, `created_at`; reasons
`purchase` / `restock` / `return` / `manual_adjustment`) as **the canonical inventory
history**, with no second accounting mechanism. Acceptance:

- every supported stock mutation generates one appropriate ledger event;
- pytest plus a live stock-mutation flow.

The full-audit definition adds:

- a canceled order's rows net to zero;
- a read endpoint with an envelope behind a capability;
- `created_by` from the authenticated user, never the body;
- append-only, like B5.1b.

Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

**Followed** from `[BE-01]` `inventory_logs`:

- the columns and the four reasons;
- `created_by` is the acting user;
- the `[BE-05]` rule that inventory moves atomically with the order.

**Deliberately different:**

- **`reason` is a CHECK constraint, not a Postgres ENUM type.** Same four values;
  it avoids `ALTER TYPE … ADD VALUE` transaction limits later.
- **Extra columns: `product_id` and `order_id`.** Most products have no variant
  rows, so a movement of the product's aggregate needs `product_id`
  (`variant_id` NULL). `order_id` is what lets an order's purchase and return rows
  be matched (net to zero).
- **No foreign keys.** See the design finding below. The spec's
  `variant_id FK → product_variants` / `created_by FK → auth.users` are the
  Supabase-era sketch.
- **The stack header** (Supabase), as always.

## Recon (Rules 6–11)

**Every place stock changes:**

| Path | Movement |
| --- | --- |
| `services/checkout.py` | variant + aggregate decrement per line |
| `services/order_lifecycle.restore_stock` (via `cancel_order_tx`) | both cancel paths |
| `routers/products.py` create | opening stock |
| `routers/products.py` PATCH | absolute `stock` |
| `routers/products.py` variant create | opening stock |
| `routers/products.py` variant PATCH | absolute `stock` |

- **Nothing else moves stock.** Refunds move money only. Seeds write stock directly
  at bootstrap.
- **Variant delete** removes a counter rather than moving units, and the aggregate is
  untouched, so it is not logged.
- **R10 ("what if this runs twice?") found B6.19**: concurrent cancels restored stock
  twice. It was fixed and pushed first (P1), so the ledger can never record a double
  return.

**Design finding (no FKs).** The first version used FK `ON DELETE SET NULL` for the
variant, order and user links. The test teardown hit a real failure: one `DELETE
FROM users` that cascades to that user's orders updates the same ledger row through
two `SET NULL` actions, and Postgres raised `inventory_logs_order_id_fkey`. In
production, **deleting a customer with ledgered orders would have failed**.

A history table should keep the ids it was written with anyway, like `product_id`.
The final table therefore has **no FKs**. The read endpoint LEFT JOINs names, and
deleted references show without them. The append-only trigger can then refuse
*every* UPDATE, DELETE and TRUNCATE; B5.1b needed an FK-null exception.

The table existed only in my dev database; I dropped it there, and the clean
environment below proves the bootstrap.

**Contract:** `GET /admin/inventory/logs` (new).

- Access: `StaffCatalog` (admin, super_admin, order_manager); support and customers
  get 403, anonymous gets 401.
- Response: always a page envelope (`page`, `page_size`, default 25), newest first.
- Filters: `product_id`, `variant_id`, `order_id`, `reason` (`Literal`, otherwise
  422).
- Items: `id, product_id, product_name, variant_id, size, color, order_id,
  order_number, change_amount, reason, created_by, created_by_email, created_at`.

## What was done

- **`app/db.py` (`CATALOG_DDL`, guarded shapes from B6.16):**
  - `inventory_logs` with CHECKs: `change_amount <> 0` and `reason` in the four
    values;
  - three indexes (product + time, variant, order);
  - `inventory_logs_append_only()` plus row and TRUNCATE triggers.
- **`app/services/inventory_log.py` (new): `log_stock_change`**, the only writer
  (R7). It rejects unknown reasons and skips zero changes.
- **Callers:**

  | Caller | Reason | Change | Attribution |
  | --- | --- | --- | --- |
  | checkout (per line) | `purchase` | −qty | variant, order, customer |
  | `restore_stock` (per item) | `return` | +qty | variant, order, actor |
  | product create | `restock` | +stock | admin |
  | product PATCH with `stock` | `manual_adjustment` | new − old | admin |
  | variant create | `restock` | +stock | variant, admin |
  | variant PATCH with `stock` | `manual_adjustment` | new − old | variant, admin |

  - `cancel_order_tx` / `restore_stock` gain `actor_id`, which both order routes
    pass.
  - Both PATCH paths now read the row `FOR UPDATE`, so a checkout between the read
    and the write cannot skew the logged delta.
- **`routers/admin.py`:** the read endpoint.
- **Docs:**
  - `backend/README.md`: endpoint row and "Stock ledger" section;
  - `plan/RULES.md` canonical table and the `AGENTS.md` R7 line: stock ledger →
    `services/inventory_log.py`.

## Files changed

- `backend/app/db.py`, `backend/app/services/inventory_log.py` (new),
  `backend/app/services/checkout.py`, `backend/app/services/order_lifecycle.py`,
  `backend/app/routers/orders.py`, `backend/app/routers/products.py`,
  `backend/app/routers/admin.py`
- `backend/tests/test_inventory_log.py` (new, 9 tests), `backend/tests/api_smoke.py`
  (+2 checks)
- docs:
  - `backend/README.md`, `plan/RULES.md`, `AGENTS.md`;
  - this audit;
  - `plan/MASTER-BACKLOG.md` (+F5.19), `plan/frontend-tasks.md` (+F5.19),
    `plan/session-log.md`, `plan/README.md`.

## How to verify

`pytest tests/test_inventory_log.py`: **9 passed**.

- **Opening stock:** the product's 10 and the variant's 4 are `restock` rows by the
  admin.
- **Checkout M×2 (variant) + L×1 (no variant):** `purchase` −2 with the variant and
  −1 without it, by the customer. The customer's cancel then adds `return` +2 / +1
  with the same variant. The order **nets to zero** and the stock is back.
- **Staff cancellation:** the `return` is attributed to the staff member.
- **B6.19 interplay:** a stale second cancel logs no second return.
- **Manual adjustments:**
  - product 10 → 7 gives −3; variant 4 → 9 gives +5 with the variant;
  - a PATCH without `stock`, or with the same value, logs nothing.
- **Failed checkout:** a 409 stock conflict leaves no `purchase` row (same
  transaction).
- **Append-only:** UPDATE, DELETE and TRUNCATE are refused; a bad `reason` fails the
  CHECK.
- **Deleting references:** deleting the customer (cascading to the order) and the
  variant leaves the rows **exactly as written**.
- **Endpoint:**
  - envelope; newest first; product name and size joined; `order_number` joined;
  - `reason` filter; `reason=theft` → 422;
  - support and customer → 403; anonymous → 401.

**Negative control:** `HEAD`'s checkout, lifecycle, orders and products files (no
writer calls) fail **8 of 9**. Only the failed-checkout test passes, trivially.

**Live flow (smoke):** the smoke's real checkout → admin cancel leaves `[('purchase',
−1), ('return', 1)]` for that order (net 0), and support gets 403 on the ledger.

Full gates (dev stack):

- `ruff` clean;
- `pytest -q` **255 passed**;
- smoke **245/0**.

**Clean environment (R14):**

- `docker compose down -v && up -d --build`;
- `db-init` exits 0 with **4** stages; `/health` ok;
- `psql` shows the 8 columns, **0** foreign keys, the two triggers, the four indexes
  and 0 rows (seeds predate the ledger);
- then `pytest -q` **255 passed** and smoke **245/0** on the clean stack.

**Verification level:** clean-environment tested.

## What is NOT done / open

- **F5.19 (new, P3): an admin ledger viewer** (e.g. on `/admin/inventory`, with
  `AdminDataTable`). The API is ready.
- **Seeded / pre-existing stock has no opening rows.** The ledger starts with the
  first movement after deploy. A ledger sum is therefore a history, not a stock
  reconciliation.
- **Variant deletion is not logged** (a counter removed, no units moved).
- `infra/README.md`, frontend docs: untouched (no UI change).
