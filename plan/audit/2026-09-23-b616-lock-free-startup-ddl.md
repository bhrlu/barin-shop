# Audit — B6.16 Startup DDL no longer locks or deadlocks traffic (2026-09-23)

## Task

`B6.16` (P2, Batch C), discovered while verifying B5.4b: `startup_ddl()` runs on every
backend boot and in every `db-init` seed job, and issued `ALTER TABLE … ADD COLUMN IF
NOT EXISTS` (ACCESS EXCLUSIVE lock even when the column exists) and `CREATE INDEX IF NOT
EXISTS` (SHARE lock) on hot tables. A restart under traffic blocked requests and could
deadlock them — captured: `DeadlockDetectedError` between `GET /products`
(AccessShareLock) and the booting backend (AccessExclusiveLock) → 500. Taken ahead of
B6.9a because every backend edit in this run reloads the dev container, so the defect
made all later verification unreliable.

## Spec check (Rule 0)

Not covered by the spec (infrastructure). Rule 14 (clean-environment proof) applies.

## What was done (`backend/app/db.py`)

- `_DDL_GUARDS` + `ddl_needed(conn, stmt)`: for the four DDL shapes the module uses —
  `ALTER TABLE public.<t> ADD COLUMN IF NOT EXISTS <c>`, `CREATE [UNIQUE] INDEX IF NOT
  EXISTS <i>`, `CREATE TABLE IF NOT EXISTS public.<t>`, `ALTER TYPE public.<t> ADD VALUE
  IF NOT EXISTS '<v>'` — a catalog query (`information_schema.columns`, `to_regclass`,
  `pg_enum`) decides whether the statement is needed; it runs only if its object is
  missing. Anything else (the two backfill `UPDATE`s, the settings-row `INSERT` — row
  locks only) still always runs, exactly as before.
- The transactional DDL now takes `pg_advisory_xact_lock('ddl')` first (backend boot,
  seed jobs and tests serialize; waiting for it is unbounded) and then `SET LOCAL
  lock_timeout = '10s'`, so a DDL that is really needed waits at most 10 s for its
  table lock instead of queueing every request behind it.
- No statement text changed; `startup_ddl()` stays idempotent and callable from seeds.

## Files changed

`backend/app/db.py`, `backend/tests/test_startup_ddl.py` (new), `backend/README.md`,
`plan/RULES.md`; docs: this audit, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`,
`plan/session-log.md`, `plan/README.md`.

## Verification results

| Check | Result |
|---|---|
| `tests/test_startup_ddl.py` | **4 passed** — every DDL statement of the four shapes is covered by a guard (so a new unguarded shape fails CI); the catalog check reports 4 existing objects as present and 4 invented ones as missing; **a steady-state boot finishes while another transaction holds ROW EXCLUSIVE on products/orders/order_items/payments/coupons/refund_requests/users**; 3 concurrent boots + 6 concurrent queries → no exception |
| **Mutation control** (guards disabled = old always-run behaviour) | the busy-tables test times out and the catalog test fails (2 failed) |
| Reproduction probe (in-process `GET /products` while forcing container reloads) | before: `DeadlockDetectedError` within ~80 requests; after: **300 requests, 12 reloads, 0 failures** |
| Tests during forced reloads (the loop that failed before at iteration 4) | **8/8 iterations clean** |
| full `pytest -q` / `ruff` / `api_smoke.py` | **190 passed** / clean / **229 checks, 0 failed** |
| **Clean environment** (`down -v && up -d --build`) | `db-init` exit 0, four stages; `/health` OK; **schema identical** to the pre-change snapshot — 195 columns (name, type, nullability, default), 55 indexes (full definitions), 5 enum labels |

**Verification level: fully verified.**

## What is NOT done / open

- The guard recognises the four shapes above; a future DDL in another shape (e.g.
  `ALTER TABLE … ADD CONSTRAINT`) must add a guard — the coverage test fails until it
  does, and `plan/RULES.md` now says so.
- Real schema migrations still take their locks (bounded by `lock_timeout`); if one
  times out under heavy load the boot fails loudly and the container restart retries.
