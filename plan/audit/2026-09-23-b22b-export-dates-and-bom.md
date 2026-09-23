# Audit — B2.2b Export date/encoding correctness (2026-09-23)

## Task

`B2.2b` (P3, Batch C), found during AB-FE-02. Three problems:

- **Offset dropped.** `services/exports.py::parse_range` used
  `.replace(tzinfo=UTC)`, so `from=2026-09-22T00:00:00+03:30` was read as UTC
  midnight.
- **No BOM.** CSV exports had none, so Excel garbles Persian when it opens the file
  directly.
- **English errors.** A bad date gave an English 422.

Required:

- convert aware input with `astimezone(UTC)` and keep naive input as UTC (the UI's
  format);
- add a BOM;
- return Persian 422s;
- keep the exclusive `to` and the rest of the contract.

Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

`[BE-08]` exports: CSV/XLSX with customer and item detail. No conflict. The stack
header is ignored.

## Recon / contract (Rules 6–8)

- **Callers:** `routers/exports.py::_range_or_400` wraps `parse_range` for
  `orders.csv`, `orders.xlsx` and `report`, and turns a `ValueError` into a 422 with
  `str(exc)`.
- **CSV builder:** `_csv()` backs both `orders.csv` and `products.csv`.
- **Consumers:**
  - the admin UI (`ExportControls`) downloads blobs and sends offset-less UTC
    bounds, so it is unaffected;
  - the smoke test compared the first line with `startswith("order_number,…")`, and
    httpx's utf-8 decode keeps a BOM, so those checks now strip it, and a new check
    asserts it.
- **Contract:** response shapes, file names and `to` exclusivity are unchanged. The
  CSV now has 3 leading bytes (EF BB BF). The 422 detail is now Persian.

## What was done

- **`services/exports.py`:**
  - `_instant()`: `fromisoformat`; aware → `astimezone(UTC)`, naive → UTC; a bad
    value → «تاریخ شروع/پایان نامعتبر است: …»;
  - `parse_range` uses it; an inverted or empty range →
    «تاریخ شروع باید پیش از تاریخ پایان باشد»;
  - `_csv()` writes a `﻿` BOM first.
- **`tests/api_smoke.py`:** the header checks strip the BOM; +1 check that the CSV
  starts with the BOM bytes.
- **`tests/test_exports.py` (new, 9 tests).**

## Files changed

- `backend/app/services/exports.py`
- `backend/tests/test_exports.py` (new), `backend/tests/api_smoke.py`
- docs: `backend/README.md` (export row), this audit, `plan/MASTER-BACKLOG.md`,
  `plan/backend-tasks.md`, `plan/session-log.md`, `plan/README.md`

## How to verify

`pytest tests/test_exports.py`: **9 passed**.

- **Parser:**
  - naive input stays UTC;
  - `+03:30` converts: 00:00 is 20:30 UTC the day before;
  - `Z` works;
  - an inverted or equal instant gives the Persian error;
  - bad `from` / `to` give the Persian errors;
  - the default window is 30 days.
- **HTTP:**
  - an order created at 2026-01-10T21:00Z (00:30 on the 11th in Tehran) is in the
    `+03:30` window for the 11th and not in the one for the 10th;
  - a bad date and an inverted range give a Persian 422 on `orders.csv` and `report`;
  - both CSVs start with the BOM; XLSX is still a plain zip (`PK`).

**Negative control:** with `HEAD`'s `exports.py`, **7 of 9 fail**. Only the naive
and default-window tests pass, as they should.

Full gates:

- `pytest -q` **287 passed**; `ruff` clean;
- smoke **253/0**, including the new BOM check.

**Browser (the AB-FE-02 flow):** the order and product export panels download
CSV (BOM plus header) and Excel (zip). 5/5, no page errors.

**Verification level:** integration tested + browser tested.

## What is NOT done / open

- **XLSX is unchanged.** Excel files have no encoding problem.
- **The UI keeps sending naive UTC bounds.** It does not need offsets.
