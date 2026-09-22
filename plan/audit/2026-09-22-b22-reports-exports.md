# Audit — 2026-09-22 — B2.2 reports & exports (spec BE-08)

## Task

**B2.2** from `plan/backend-tasks.md`: daily/monthly sales reports, best-sellers,
Excel + CSV export of orders (and product catalog). Corresponds to spec
`[BE-08] exportOrders({ fromDate, toDate, status?, format })`.

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` before starting. [BE-08]'s signature is
implemented as REST query params (`/admin/export/orders.{csv|xlsx}?from=&to=&status=`)
since the repo is FastAPI-only (standing adaptation; the spec's Supabase RPC
shapes are consistently mapped to REST here). "Tax/discount splits" ships as
`discount` + `shipping` + `total` columns — the store has no tax field in the
order model, noted as a model gap, not silently invented. Rule-4 statuses are
exported verbatim; no money rules touched.

## What was done

**New `app/services/exports.py`**
- `fetch_orders` — joins users/profiles, aggregates items into one cell
  (`name / size / color × qty | …`), splits the jsonb shipping address into
  city / address / postal_code columns; filters `from` ≤ created_at < `to`,
  optional `status`.
- `fetch_products` — full catalog with stock + low-stock threshold.
- CSV via stdlib `csv` (RFC-4180 quoting — Persian text safe); XLSX via
  openpyxl in-memory (`Workbook`, one sheet, 31-char title cap).
- `Content-Disposition` is RFC 6266-compliant: ASCII `filename=` +
  `filename*=UTF-8''` Persian name, timestamped (`sande-orders-20260922-0945.csv`).
- `sales_report` — daily & monthly revenue (cancelled excluded) + top-10
  best-sellers by units.
- `parse_range` — ISO dates, defaults to last 30 days, 422 when `from ≥ to`.

**New `app/routers/exports.py`** (mounted in `main.py`) — all under
`/admin/export`, guarded by `StaffOrders` (admin/super_admin/order_manager per
the B5.4 matrix): `orders.csv`, `orders.xlsx`, `products.csv`, `products.xlsx`,
`report` (JSON). `pyproject.toml` gains `openpyxl>=3.1`.

## Files changed

- `backend/pyproject.toml` (openpyxl dep)
- `backend/app/services/exports.py` (new)
- `backend/app/routers/exports.py` (new)
- `backend/app/main.py` (router mount)
- `backend/tests/api_smoke.py` (B2.2 section: 10 checks)
- Docs: this audit, task tick, session log 29, `backend/README.md`, roadmap

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q        # 39 passed
./.venv/bin/python -m ruff check app tests           # clean
./.venv/bin/python tests/api_smoke.py                # 186 checks, 0 failed
cd infra && docker compose up -d --build backend     # picks up openpyxl
```

Live: `orders.csv` → 72 lines with proper header & Persian content;
`orders.xlsx`/`products.xlsx` → `PK` zip magic, ~10.8 KB; `report` → 4 daily
buckets + 8 best-sellers; `from ≥ to` → 422; anonymous → 401; `support` token
→ 403 (capability matrix holds).

Two container-specific fixes made en route: `:status::text` (double-colon
cast) is illegal under asyncpg's bind parser → `CAST(:status AS text)`; the
backend image had to be rebuilt for openpyxl (volume-mounted code, baked deps).

## What is NOT done / open

- **CSV product *import*** (the task text mentions it) is not implemented —
  one-direction export first; import needs an idempotency/overwrite policy the
  user hasn't chosen. Left as a new checkbox on `plan/backend-tasks.md`.
- No streaming for very large windows (rows are materialized; the catalog is
  small). Revisit if exports exceed ~10⁵ rows.
- The frontend has no export button yet — natural home is the F4.3 data-grid
  toolbar (spec puts CSV/Excel export there). Filed as a checkbox on
  `plan/frontend-tasks.md`.
- PDF invoices (B2.3) remain open — the F4.4 print stylesheet already covers
  the shop-side invoice need.
