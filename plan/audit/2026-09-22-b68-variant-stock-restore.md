# B6.8 — Per-variant stock restoration on cancellation

**Date:** 2026-09-22
**Task ID:** `B6.8` (P0 — Correctness, `plan/MASTER-BACKLOG.md`; source
checkbox `plan/backend-tasks.md`)
**Title:** Per-variant stock restoration on cancellation

## Original requirement

Variant orders decrement `product_variants.stock`, but cancellation restored only
the product aggregate, silently corrupting inventory. The backlog asks for:

1. an idempotent `order_items.variant_id` column through the canonical additive
   DDL path;
2. seed jobs able to apply that DDL independently;
3. `line["variant_id"]` persisted during checkout;
4. variant **and** aggregate stock restored in one transaction;
5. aggregate-only behaviour preserved for legacy `NULL` variant rows;
6. repeated cancellation remaining a no-op.

## Spec check (Rule 0)

* **`[BE-05]` Order Lifecycle Management** — *followed*. "Restore stock on
  cancellation … atomic database transaction to safeguard inventory consistency"
  is exactly this change; the restore runs inside the caller's transaction, next
  to the status flip, and the existing `audit_logs` entry is unchanged.
* **`[BE-01]` Product Variants Matrix** — *partially followed*. The repo's
  `product_variants` uses `color` (not `color_name` / `color_hex`), has no
  `price_override`, and there is no `inventory_logs` table. The live repo wins
  (Rule 0.2); reshaping the variant table is out of B6.8's scope and would break
  `app/services/variants.py`, the admin variant CRUD and the seeds. The new FK
  points at the repo's real column set.
* **Spec stack header (Supabase / RLS / `createServerFn`)** — *deliberately
  ignored*. This repo is FastAPI-only with its own JWT; the DDL lives in
  `startup_ddl()`, not in a Supabase migration.
* **Rule 4 vocabulary** — no status string and no money rule was touched.

## Repository architecture check (Rule 6)

* **Owning module:** `backend/app/db.py` (additive DDL),
  `backend/app/services/checkout.py` (write path),
  `backend/app/services/order_lifecycle.py` (restore path — already
  variant-aware, left unchanged).
* **Data flow:** `POST /checkout` → `routers/checkout.py` → `services/checkout.py`
  → `public.order_items` / `public.product_variants`; cancellation:
  `POST /orders/{id}/cancel` **and** `PATCH /orders/{id}` (status `cancelled`) →
  `routers/orders.py` → `services/order_lifecycle.cancel_order_tx` →
  `restore_stock` → the same two tables.
* **API contract (Rule 8):** unchanged. No request or response shape, status
  code, error body or pagination envelope moved; `variant_id` is an internal
  column and is not exposed by any endpoint.
* **Auth (Rule 9):** unchanged. `POST /checkout` and `POST /orders/{id}/cancel`
  stay on `CurrentUser` with the existing ownership filter in `_fetch_order`;
  `PATCH /orders/{id}` stays on `StaffOrders`. Nothing the client sends can
  choose a `variant_id` — it is resolved server-side from the locked variant row.
* **Canonical implementation (Rule 7):** no new helper. `restore_stock()` in
  `order_lifecycle.py` already read `order_items.variant_id`; the column simply
  never existed, so its `information_schema` guard always took the
  aggregate-only branch. The fix supplies the missing column and the missing
  write, rather than adding a second restore path.
* **Blast radius:** `grep -rn variant_id` covers `services/checkout.py`,
  `services/order_lifecycle.py` and the variant CRUD in `routers/products.py`
  (which uses the unrelated path parameter of the same name). No frontend
  consumer: `src/lib/api.ts` never reads `order_items.variant_id`.
* **State machine (Rule 10):** `ALLOWED_STATUS_TRANSITIONS` and
  `CANCELLABLE_STATUSES` untouched. A repeat `POST /cancel` still short-circuits
  on `status == 'cancelled'` before reaching `cancel_order_tx`; a repeat
  `PATCH … status=cancelled` still raises `CancelError` → 409. Neither path
  restores stock twice — verified live below.

## Files changed

* `backend/app/db.py` — `CATALOG_DDL` gains
  `ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS variant_id UUID
  REFERENCES public.product_variants(id) ON DELETE SET NULL`, placed after the
  `product_variants` table it references. Every seed module already calls
  `startup_ddl()` (`seed_auth`, `seed_products`, `seed_demo`, `seed_coupons`,
  `seed_mock`), so requirement 2 needed no change.
* `backend/app/services/checkout.py` — the `order_items` INSERT now carries
  `variant_id` (cast from the resolved variant, `NULL` when the product has no
  matrix row for that size × color).
* `backend/tests/test_order_lifecycle_stock.py` — **new** DB-backed test module
  (Rule 11) covering the four acceptance tests.

`backend/app/services/order_lifecycle.py` was deliberately **not** modified: it
already restores variants first and the aggregate second, and its
`information_schema` guard keeps a stack whose DDL has not yet run from
crashing (Rule 12, minimal diff).

## Implementation summary

Checkout already resolved and locked the variant row and decremented its stock,
but threw the identity away when writing the order line, so cancellation had no
way to find it. The column now exists and is written, which switches
`restore_stock()` onto its already-correct variant branch. Lines with no variant
row keep `variant_id = NULL` and still bump only `products.stock`.

## Tests executed

```
cd backend
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres \
  ./.venv/bin/python -m pytest -q tests/test_order_lifecycle_stock.py   # 5 passed
DATABASE_URL=… ./.venv/bin/python -m pytest -q                          # 44 passed
./.venv/bin/python -m ruff check app tests                              # All checks passed
./.venv/bin/python tests/api_smoke.py                                   # 196 checks, 0 failed
```

New tests (`tests/test_order_lifecycle_stock.py`, skipped when no database is
reachable so the pure-unit suite still runs anywhere):

* checkout decrements aggregate **and** variant stock;
* the order line persists the resolved `variant_id`;
* cancellation restores both to their original values;
* a second cancellation raises `CancelError` and inflates neither value;
* a line with no variant row stores `NULL` and restores the aggregate only.

**Mutation check:** with the new `variant_id` binding forced back to `None`,
three of the five tests fail — the tests genuinely cover the defect rather than
passing vacuously.

### Clean-environment verification (Rule 14)

```
cd infra && docker compose down -v && docker compose up -d --build
docker compose logs db-init     # exit 0, all four seed stages (auth, products, demo, coupons)
docker compose ps               # postgres + minio healthy, backend healthy
curl -fsS http://localhost:8000/health   # {"ok":true,…}
psql \d public.order_items      # variant_id uuid + order_items_variant_id_fkey … ON DELETE SET NULL
```

### Live runtime flow (fresh stack, real HTTP)

Variant `XS / مشکی` created on `tshirt-1` via `POST /products/{id}/variants` as
admin; product stock 25, variant stock 6.

| step | (product, variant) |
| --- | --- |
| before | (25, 6) |
| `POST /checkout` qty 2 | (23, 4) |
| `POST /orders/{id}/cancel` | (25, 6) |
| repeat `POST /cancel` (200, no-op) | (25, 6) |
| checkout of a colour with **no** variant row, qty 1 | (24, 6) |
| cancel it | (25, 6) |
| admin `PATCH /orders/{id}` → `cancelled`, qty 3 | (22, 3) → (25, 6) |
| repeat `PATCH` → 409 «قابل لغو نیست» | (25, 6) |

The test variant and the three cancelled test orders were deleted afterwards;
`tshirt-1` is back at its seeded stock of 25.

## Verification level

**Fully verified** — unit/integration tests pass, full backend suite and ruff
pass, `api_smoke.py` passes against the running stack, the behaviour was
exercised over real HTTP on both cancel entry points, and the DDL was proven from
a `docker compose down -v` clean environment.

## Remaining limitations

* **No backfill for historical rows.** Orders placed before this change keep
  `variant_id = NULL`; cancelling them restores the aggregate only, exactly as
  today. A retroactive match on `(product_id, size, color)` would be a guess when
  the matrix has changed since, so it was not attempted.
* **Restock still has no ledger.** The spec's `[BE-01]` `inventory_logs` table
  does not exist, so stock movements are not individually auditable (the
  cancellation itself is recorded in `audit_logs`).
* **No aggregate/variant consistency check.** Nothing prevents an admin from
  editing `products.stock` and `product_variants.stock` out of step; that is
  pre-existing behaviour, untouched here.
* `order_lifecycle.restore_stock()` still queries `information_schema` on every
  cancellation. Now that the DDL always adds the column the check is redundant,
  but removing it is a separate cleanup (see follow-up).

## Related follow-up findings

Recorded in the Master Backlog task index as discovered-during-B6.8:

* `NEW-B68-1` (P3) — drop the now-redundant `information_schema` probe in
  `restore_stock()` once every deployed stack has run the new DDL.

No unrelated bug was fixed in this task (Rule 12).
