# Audit — AB-BE-02 Variant SKU / price override / colour (2026-09-23)

## Task

`AB-BE-02` (P2, Batch C; blocks AB-FE-03). Spec `[BE-01]` gives each variant a
unique SKU, a nullable `price_override` and `color_hex`.

Acceptance, per the full-audit definition in
`plan/audit/2026-09-22-full-backlog-audit.md` §AB-BE-02:

- a duplicate non-null SKU is a clean 409, not a 500;
- an override prices the line through `POST /stock/check`, `POST /checkout` and the
  cart quote, with a test;
- NULL rows behave exactly as today;
- the override comes from the database only, never from the checkout body;
- idempotent DDL and a clean bootstrap.

Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

**Followed** from `[BE-01]`:

- `sku` unique and indexed;
- `color_hex`;
- nullable `price_override`;
- the unique `(product_id, size, color)` already existed.

**Deliberately different:**

- **`price_override` is `INTEGER`, not NUMERIC.** All money in this repo is integer
  tomans (`products.price`, `orders.*`, `order_items.price`); a NUMERIC column would
  be the only non-integer amount (R11).
- **The column stays `color`, not `color_name`**, so no rename (R12, and the Rule-4
  spirit of not breaking stored strings).
- **`inventory_logs` is AB-BE-01**, not this task.
- **The stack header** (Supabase) is ignored.

## Recon / contract (Rules 6–11)

**Data flow.** Variant CRUD lives in `routers/products.py` (`StaffCatalog`).
`services/variants.py` (`load_variants`, `variant_stock`) is shared by
`routers/stock.py` and `services/checkout.py`. Checkout used to take
`line["price"] = products.price`, and stock-check summed `products.price`.

**Other price readers.** `services/coupons.py` takes the subtotal it is given. Orders,
refunds and exports read the stored `order_items.price` and order totals. Nothing
else prices a line.

**Data.** The dev database had 0 variant rows; `seed_mock` (manual, not part of
`db-init`) creates 14. Its SKUs were
`f"{PID}-{size}-{abs(hash(color)) % 1000:03d}"`. Python randomises string hashes per
process, so they were nondeterministic, and with a unique index a rare collision
would have failed the seed.

**Contract.**

- `ProductVariantIn`: `price_override` > 0 or null; `color_hex` `#rrggbb` or null;
  `sku` stripped, and a blank one becomes null.
- `ProductVariantUpdateIn`: omitted or null means unchanged. `sku: ""`,
  `price_override: 0` and `color_hex: ""` clear (F5.16 convention).
- `ProductVariantOut`: `+price_override`, `+color_hex`.
- 409 on a duplicate SKU: «این SKU قبلاً برای تنوع دیگری ثبت شده است». The
  size×colour duplicate keeps its own message.
- 422 on invalid values.
- `GET /products/{id}/variants` (public) now also shows `price_override` and
  `color_hex`; prices are public anyway.

**Security (R9) / money (R11).**

- The unit price comes from the locked product and variant rows. Extra fields on a
  checkout line (for example `price: 1`) are ignored, and a test sends one.
- The override flows into `order_items.price`, so coupon discount, shipping and total
  use the overridden subtotal.
- Only catalog staff can set it (existing `StaffCatalog`).
- Changes are audited (`create_variant` / `update_variant` old and new values).

**State and idempotency (R10).** The DDL is guarded (B6.16 shapes: `ADD COLUMN IF NOT
EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`). Two normalising `UPDATE`s run before
the index:

- blank SKU → NULL;
- a later duplicate SKU → NULL, and the earliest row keeps it.

The index can therefore always be built on any database, and both statements are
no-ops afterwards.

## What was done

- **`app/db.py` (`CATALOG_DDL`):**
  - `price_override INTEGER CHECK (> 0)`;
  - `color_hex TEXT CHECK (~ '^#[0-9a-fA-F]{6}$')`;
  - the two SKU normalisations;
  - `product_variants_sku_key` UNIQUE on `sku` WHERE `sku IS NOT NULL`.
- **`services/variants.py`:** `load_variants` also reads `price_override`. New
  `variant_price(product_row, variant)` is the one canonical unit-price rule (R7).
- **`services/checkout.py` and `routers/stock.py`:** price lines with
  `variant_price`.
- **`schemas.py`:** the variant In / UpdateIn / Out fields and validators above.
- **`routers/products.py`:**
  - the variant columns;
  - INSERT and PATCH of the new fields, with clear semantics;
  - audit values;
  - `_variant_conflict()` picks the 409 message by the violated constraint.
- **`services/db_errors.py`:** `violated_constraint(exc)` reads Postgres's
  `constraint_name`.
- **`app/seed_mock.py`:** deterministic SKUs `"{PID}-{size}-{nn}"`, unique per
  product row.
- **`src/lib/api.ts`:** `ProductVariant` and `ProductVariantInput` gain
  `price_override` / `color_hex`. Types only; no UI change.

## Files changed

- `backend/app/db.py`, `backend/app/schemas.py`, `backend/app/routers/products.py`,
  `backend/app/routers/stock.py`, `backend/app/services/checkout.py`,
  `backend/app/services/variants.py`, `backend/app/services/db_errors.py`,
  `backend/app/seed_mock.py`
- `backend/tests/test_variant_fields.py` (new, 13 tests)
- `vogue-vintage-vibes/src/lib/api.ts`
- docs:
  - `backend/README.md` (variant rows + "Variant price");
  - `plan/RULES.md` (canonical table: `variant_price`);
  - this audit;
  - `plan/MASTER-BACKLOG.md` (+F5.18; AB-FE-03 now also depends on F5.18),
    `plan/frontend-tasks.md` (+F5.18), `plan/backend-tasks.md`,
    `plan/session-log.md`, `plan/README.md`.

## How to verify

`pytest tests/test_variant_fields.py`: **13 passed**.

- **DDL:** columns, types and the partial unique index exist; a second
  `startup_ddl()` is a no-op.
- **Create:** returns the new fields, and the SKU is stripped. `GET …/variants` shows
  them.
- **SKU conflicts:**
  - a duplicate SKU on **another product** → 409 with the SKU message;
  - the size×colour duplicate keeps its message;
  - a PATCH onto a taken SKU → 409.
- **Blank SKUs:** `""` and `"   "` become NULL and never collide.
- **Invalid values → 422:** `price_override` 0 or −5; `color_hex` `red` or `#12345`.
- **PATCH:** omitted fields unchanged; `0` / `""` / `""` clear; set again; the audit
  records old `{price_override: null}` and new `{price_override: 70000}`.
- **Pricing:** M with override 80 000 × 2, L with a variant but no override, S with
  no variant row:
  - `POST /stock/check` subtotal = 360 000;
  - `POST /checkout` with an injected `price: 1` per line: subtotal 360 000 (= the
    quote), total 449 000;
  - `order_items.price` = M 80 000, L 100 000, S 100 000.
- **NULL override:** priced exactly as the product (750 000).
- **Coupon:** a 10 % coupon on an overridden 200 000 line → discount 20 000.
- **Migration path:** inside a rolled-back transaction, drop the index, insert
  duplicate and blank SKUs, then replay the real `CATALOG_DDL` statements. The
  earliest row keeps its SKU, the others become NULL, and the index builds.

Negative controls:

| Variant | Result |
| --- | --- |
| `HEAD`'s `checkout.py` + `stock.py` (product price only) | 2 fail (quote/order, coupon) |
| no constraint-based conflict message | 1 fails (the SKU 409 message) |

Full gates:

- **Dev stack:** `ruff` clean, `pytest -q` **229 passed**, smoke **235/0**.
- **Clean environment (R14):**
  - `docker compose down -v && up -d --build`;
  - `db-init` exits 0 with **4** stages and `/health` is ok;
  - `psql` shows `price_override:integer`, `color_hex:text`, both CHECK constraints
    and `product_variants_sku_key … WHERE (sku IS NOT NULL)`;
  - `python -m app.seed_mock` run **twice**: 14 variants, 14 distinct SKUs, and the
    second run is a no-op;
  - then `pytest -q` 229 passed and smoke 235/0 on the clean stack.
- **Frontend:** `prettier`, `tsc` clean; `bun run lint` 0 errors / 14 warnings
  (unchanged).

**Verification level:** clean-environment tested.

## What is NOT done / open

- **F5.18 (new, P2): the storefront does not display overrides.**
  - The product page shows `products.price` for every variant.
  - The cart and checkout subtotals (`useCartSubtotal`) use catalogue prices, and the
    cart's coupon check sends that display subtotal.
  - The server charges the override correctly, but the displayed total would differ
    from the charged one.

  No UI sets an override yet (API only), so nothing live is affected. AB-FE-03, the
  editor that would expose the field, now depends on F5.18.
- **Inventory ledger:** `inventory_logs` is AB-BE-01.
- **SKU case:** uniqueness is case-sensitive, exact after trimming.
