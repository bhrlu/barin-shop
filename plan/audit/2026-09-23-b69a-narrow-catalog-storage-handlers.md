# Audit — B6.9a Narrow the remaining broad exception handlers (2026-09-23)

## Task

`B6.9a` (P2, Batch E; discovered as `NEW-B69-1` during B6.9): four handlers in
`routers/products.py` reported **any** failure as a duplicate 409
(«این ترکیب سایز و رنگ قبلاً ثبت شده است») or a generic 400, and two in
`routers/storage.py` reported any exception as a 502 or a silent `url: null`.
Since B5.1d a failed audit insert raises inside those `try` blocks too — so it was
also being reported as "duplicate".

## Spec check (Rule 0)

Not covered by the spec (error handling); `[BE-04]` audit behaviour from B5.1d kept.

## What was done

- New `app/services/db_errors.py::is_unique_violation` (SQLSTATE 23505) — moved from
  `routers/orders.py`, which keeps `_is_unique_violation` as an alias for the B6.9
  tests (one implementation, R7).
- `products.py` — create/update variant, create/update product: `except IntegrityError`;
  23505 keeps the handler's existing answer (409 / 409 / 400 / 400, same messages);
  anything else is logged and **re-raised** (500 via the error middleware). Non-integrity
  errors are no longer caught at all.
- `storage.py` — `_STORAGE_ERRORS = (MinioException, urllib3 HTTPError, OSError)`: those
  keep the 502 / `url: null`; any other exception (a programming error — the comment in
  that file records one that used to hide there) surfaces as a 500. Sign failures are
  now logged.

## Files changed

`backend/app/services/db_errors.py` (new), `backend/app/routers/products.py`,
`backend/app/routers/storage.py`, `backend/app/routers/orders.py`,
`backend/tests/test_catalog_errors.py` (new); docs: this audit, `plan/backend-tasks.md`,
`plan/MASTER-BACKLOG.md`, `plan/session-log.md`, `plan/README.md`.

## Verification results

Faults are injected with a temporary trigger that raises a chosen SQLSTATE for marker
rows only (dropped in teardown; none left behind), and with a fake MinIO client.

| Check | Result |
|---|---|
| `tests/test_catalog_errors.py` | **7 passed** — product create: `unique_violation` → 400 (kept), `check_violation` → 500, a plain raise → 500, a normal product → 201; product update: 23505 → 400, check → 500; variant: real duplicate → 409 (kept), check → **500 (was "duplicate")**, moving onto an existing size×colour → 409, check on update → 500; storage: none / `MinioException` / `OSError` → 200 / 502 / 502 and signed URL / `null` / `null`; a programming error (`AttributeError`) → 500 on both endpoints (was 502 / silent `null`) |
| **Negative control** (previous routers) | 4 failed (every fault case), 3 passed (the must-stay storage answers) |
| B6.9 tests through the alias | pass |
| full `pytest -q` / `ruff` / `api_smoke.py` | **197 passed** / clean / **229 checks, 0 failed** |

**Verification level: integration tested.**

## What is NOT done / open

- Other routers were not audited for broad handlers beyond the two files named by the
  task.
