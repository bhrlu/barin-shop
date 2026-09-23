# Audit — B5.1c Malformed `admin_id` on the audit-log endpoint (2026-09-23)

## Task

`B5.1c` (P3, Batch C), found during F5.5. `GET /admin/audit-logs?admin_id=foo`
returned 500: the string reached `CAST(:admin_id AS uuid)` and Postgres raised.
Required: type `admin_id` as `UUID | None` so FastAPI answers 422, and keep every
other filter and the response shape. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

`[BE-04]` audit log: no rule on filter validation. Nothing is in conflict; the stack
header is ignored.

## Recon / contract (Rules 6–8)

- **Owner and access:** `routers/admin.py::audit_logs` (`StaffAudit`).
- **Only UI caller:** `api.adminAuditLogs` sets `admin_id` only when it is non-empty
  (from the staff dropdown), so it always sends a real UUID.
- **Contract:** 200 responses are unchanged. A malformed `admin_id` is now FastAPI's
  standard 422 (`uuid_parsing`).
- **Edge:** `?admin_id=` (empty) is now also a 422; before, it meant "no filter". No
  client sends it.

## What was done

- `admin_id: UUID | None = None`. A plain default, because ruff B008 objects to
  `Query()` defaults on non-immutable types; for a query parameter it is equivalent.
- The SQL parameter is passed as `str(admin_id)`.
- `tests/test_audit_log_filters.py` (new, 6 tests): three malformed values → 422; a
  real admin's id filters to their entries; an unknown UUID → `[]`; the other filters
  and the row shape are unchanged.
- Smoke +2 checks: `admin_id=foo` → 422; the zero UUID → 200 `[]`.

## Files changed

- `backend/app/routers/admin.py`
- `backend/tests/test_audit_log_filters.py` (new), `backend/tests/api_smoke.py`
- docs: `backend/README.md` (audit-logs row), this audit, `plan/MASTER-BACKLOG.md`
  (+B6.20), `plan/backend-tasks.md` (+B6.20), `plan/session-log.md`,
  `plan/README.md`

## How to verify

- `pytest tests/test_audit_log_filters.py`: 6 passed. **Negative control** with
  `HEAD`'s `admin.py`: the 3 malformed cases fail (500).
- `pytest -q` **277 passed**; `ruff` clean.
- Smoke **245/0**, including both new checks.
- **Why the smoke total fell from 247 to 245:** the smoke's contact-inbox block
  (mark-answered, bogus-status 422, cleanup) runs only when a `new` message exists.
  The smoke's own `POST /contact` hits the per-IP limit (5 per 10 minutes) when runs
  are back to back, so that block was silently skipped (6 entries): 247 + 4 new − 6.
  Recorded as **B6.20**.

**Verification level:** integration tested.

## What is NOT done / open

- **B6.20 (new, P3):** make the smoke's contact-inbox checks deterministic. It should
  say they were skipped, or seed its own message, instead of silently shrinking the
  run.
- Frontend: untouched.
