# Audit — 2026-09-25 · B2.2a CSV product import

## Task

Continuous backlog execution, second task — selected from the canonical JSON
index after F3.4b: **B2.2a — CSV product import** (Batch F, P3, backend,
resolved decision D3). Idempotent upsert from CSV: `product_id` canonical key
when supplied, otherwise normalized `name + category`; only supplied columns
update; in-file duplicates rejected; transactional; retry-safe.

## Spec check (Rule 0)

- Section-scoped: D3 (matching order, deterministic normalization, partial
  update, duplicate rejection, transactional retry) is the governing decision
  and is implemented as written. `[BE-01]`'s inventory discipline is respected
  via the canonical ledger service. Spec not edited.
- Followed: Rules 0–5; Part B 6, 6a, 7, 8, 10, 12, 13, 15 (idempotency audit +
  ledger invariants + one-transaction state change). 11 not triggered (no
  money: prices are stored, not computed).
- Deliberately ignored: none.

## What was done

1. **New canonical service** `backend/app/services/csv_import.py` (no prior
   import path existed; the CSV machinery in `services/exports.py` is
   export-only):
   - key resolution: valid-UUID `product_id` (validated first; a bogus id is a
     422, never a raw DB error) → id-keyed upsert with **no name fallback**;
     otherwise normalized `name + category` (trim, casefold, collapse
     whitespace) via `lower(regexp_replace(...))` SQL;
   - partial update: a cell that is empty/`N/A`/`-`/`null` means "not
     supplied" and never erases the stored value;
   - in-file duplicate keys (same id, or same normalized pair) → 422 naming
     both rows, before anything is written;
   - one transaction per file: `parse_csv` fails fast on unknown headers /
     bad cells / malformed `colors` (`Name:#hex`, `|`-separated) / bad dates,
     and any DB failure rolls the whole file back;
   - new products insert with a generated UUID when id-less (`products.id` is
     TEXT without default), `is_new` defaulting to true like `POST /products`;
   - ledger discipline via `services/inventory_log.log_stock_change` (R7):
     opening stock of a new product = `restock`; a stock change on an update =
     `manual_adjustment` delta; a matched, unchanged stock writes nothing — so
     re-importing the same file is a no-op on the ledger (idempotent, R10);
   - JSONB colors are bound as a JSON string, exactly like `POST /products`.
2. **Endpoint** `POST /products/import` (`routers/products.py`,
   multipart `UploadFile`): catalog staff only (`StaffCatalog`, same guard as
   every other product mutation), one audit row `import_products` with the
   file name and `created/updated/total` counts, committed atomically with the
   import. `ACTIONS` vocabulary extended.
3. **Tests** `backend/tests/test_csv_import.py` — 11 tests: parser (BOM,
   unknown headers, normalization, in-file duplicates, id vs name keys, bad
   UUID, missing key) and live-DB behaviour (insert / update-by-id /
   update-by-normalized-name, omitted fields stay, re-import idempotent with a
   single ledger row, in-file duplicate 422 writes nothing, bad cell rolls the
   whole file back, stock delta rows, opening-stock restock, audit entry,
   support 403, anonymous 401, empty file 422).

Two environment facts surfaced while testing (behavior confirmed correct, no
code change): `products.id` is TEXT PRIMARY KEY (no default) and
`inventory_logs.product_id` is TEXT — the first service draft wrongly cast
them to UUID; the tests exposed it immediately.

## Files changed

- `backend/app/services/csv_import.py` (new)
- `backend/app/routers/products.py` (one endpoint + imports)
- `backend/app/services/audit.py` (`import_products` action)
- `backend/tests/test_csv_import.py` (new, 11 tests)
- `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
  `plan/audit/2026-09-25-b22a-csv-product-import.md` (this file)

## How to verify

```
cd backend
./.venv/bin/python -m pytest -q tests/test_csv_import.py   # 11 passed
./.venv/bin/python -m pytest -q                            # 364 passed
./.venv/bin/python -m ruff check app tests                 # clean
./.venv/bin/python tests/api_smoke.py                      # 257/0
# manual: POST /products/import (multipart file=products.csv) as catalog staff
```

CSV round-trips with the admin product export
(`GET /admin/export/products.csv` headers: `product_id, name, category, price,
old_price, stock, low_stock_threshold, active, updated_at`) for
id/price/stock/active/threshold columns.

## What is NOT done / open

- No frontend upload control — the backlog task is backend-only (the admin UI
  export buttons exist; an import button would be a new task).
- `available_at`/dates accept ISO-8601 (same as the manual editor); no
  locale-date parsing.
- Verification level: **integration tested** (live-DB tests + smoke 257/0);
  no browser involvement by nature of the task.
