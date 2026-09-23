# Audit — B5.1b Audit-log DB tamper resistance (2026-09-23)

## Task

`B5.1b` (P2, Batch C): make `audit_logs` append-only for the application — INSERT and
SELECT allowed, UPDATE and DELETE denied — verified from a clean database.

## Spec check (Rule 0)

`[BE-04]` ("tamper-resistant trail of privileged mutations") — followed. The spec's
Supabase/RLS wording is stale (Rule 0.2); enforcement is plain Postgres.

## Recon — why not REVOKE

The app connects as `sande`, which **owns** `audit_logs` and is a **superuser** in the
compose stack (`rolsuper = t`). Privileges cannot restrain either, so a `REVOKE UPDATE,
DELETE` would change nothing. Enforcement therefore uses triggers. Second constraint:
`audit_logs.admin_id` is `REFERENCES users ON DELETE SET NULL`, so deleting a user
performs an UPDATE on its audit rows — blocking every UPDATE would make users
undeletable.

## What was done

- `AUDIT_DDL` (startup, idempotent): `public.audit_logs_append_only()` + two triggers —
  `BEFORE UPDATE OR DELETE … FOR EACH ROW` and `BEFORE TRUNCATE … FOR EACH STATEMENT` —
  raising `insufficient_privilege` «audit_logs is append-only (… refused)». The only
  allowed change is exactly the FK cascade: `admin_id` → NULL with **every other column
  unchanged** (attribution lost, nothing else moves).
- `db.py` guards gained the `CREATE [OR REPLACE] FUNCTION` and `CREATE [OR REPLACE]
  TRIGGER` shapes (checked via `to_regproc` / `pg_trigger`), so B6.16's lock-free boot
  holds; `tests/test_startup_ddl.py` now requires those shapes to be guarded.
- Tests no longer delete their own audit rows (6 cleanup statements removed in
  `test_notifications`, `test_audit_atomicity`, `test_role_lockout`,
  `test_catalog_errors`, `test_coupon_update`) — append-only means that is refused;
  deleting their users still works and nulls the attribution.
- `api_smoke.py` — both copies of "audit entries carry admin identity + timestamps"
  asserted that **every** order audit row in the table has an `admin_id`. That was
  never a product guarantee (the FK has always nulled it when a user is deleted), and
  on a fresh stack the pytest suite's deleted users now leave such rows behind, so the
  check failed (2 FAIL). It now asserts the same thing for **this run's own** entries
  (its order mutations, admin `admin@sande.local`): non-empty, `admin_id`, email and
  `created_at` all present. A regression in `record_audit` still fails it.

## Files changed

`backend/app/db.py`, `backend/tests/test_audit_append_only.py` (new),
`backend/tests/test_startup_ddl.py`, `backend/tests/api_smoke.py`,
`backend/tests/{test_notifications,test_audit_atomicity,test_role_lockout,test_catalog_errors,test_coupon_update}.py`,
`backend/README.md`; docs: this audit, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`,
`plan/session-log.md`, `plan/README.md`.

## Verification results

| Check | Result |
|---|---|
| `tests/test_audit_append_only.py` | **6 passed** — INSERT via `record_audit` works; UPDATE / DELETE / TRUNCATE refused and the row unchanged; re-attributing to another user refused; nulling `admin_id` *and* editing another column refused; deleting the user nulls `admin_id` with every other column identical |
| **Negative control** (triggers dropped = the previous DB state) | `UPDATE audit_logs SET action='tampered'` affected 1 row; then `startup_ddl()` saw them missing and recreated both (the new guards), and the suite passed again |
| `tests/test_startup_ddl.py` (incl. the extended coverage test) | 4 passed |
| full `pytest -q` | **203 passed** — before and after the clean rebuild |
| **Clean environment** (`down -v && up -d --build`) | `db-init` exit 0, four stages; `/health` OK; both triggers present on the fresh DB |
| `api_smoke.py` on the clean stack | first run **2 FAIL** (the over-broad identity check above); after scoping it to the run's own entries **229 checks, 0 failed** |
| `ruff` | clean |

**Verification level: fully verified** — for tamper resistance against the application
and any non-superuser path. A superuser can still disable triggers
(`session_replication_role`) or drop them; that is inherent while the app runs as one.

## Discovered (recorded, not fixed)

- **B5.1e** (`NEW-B51B-1`, P3, infra) — the backend connects as the schema owner and a
  superuser. Run it as a least-privilege role (DML only, no DDL/ownership; DDL by a
  separate migrator role), which is also what makes the audit trail tamper-*proof*
  rather than tamper-resistant.

## What is NOT done / open

- B5.1e. Test runs now leave audit rows (with NULL attribution) in the dev DB, by design.
