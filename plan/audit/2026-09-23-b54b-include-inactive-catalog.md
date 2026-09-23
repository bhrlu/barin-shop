# Audit — B5.4b `include_inactive` follows the `catalog` capability (2026-09-23)

## Task

`B5.4b` (P2, Batch C), discovered during AB-FE-05: `GET /products?include_inactive=true`
returned inactive rows only for `AuthUser.is_admin` (admin/super_admin). An
`order_manager` holds `catalog` — may edit products — but never saw inactive ones in
`/admin/products`, so could not re-activate them.

## Spec check (Rule 0)

`[BE-04]` capability-based access — followed (capability, not a role list).

## What was done

`routers/products.py::list_products`: the inactive rows are included when
`include_inactive=true` **and** the caller `has_capability(user.roles, "catalog")`.
Everything else unchanged (flag still opt-in; anonymous / customer / support still get
active rows only).

## Files changed

`backend/app/routers/products.py`, `backend/tests/test_include_inactive.py` (new); docs:
this audit, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`, and a correction in
`plan/audit/2026-09-23-f516-coupon-edit-clear-and-kind.md`.

## Verification results

| Check | Result |
|---|---|
| `tests/test_include_inactive.py` | **7 passed** — anonymous / customer / support → active only; order_manager / admin / super_admin → active + inactive (bare list and the paginated envelope); without the flag an order_manager still gets active only |
| **Negative control** (previous router) | the order_manager case fails |
| full `pytest -q` / `ruff` / `api_smoke.py` | **186 passed** / clean / **229 checks, 0 failed** |
| Headless Chromium | **3/3** — order_manager and admin see an inactive product on `/admin/products`; `/shop` does not list it |

**Verification level: browser tested** (+ integration).

## Discovered (recorded, not fixed) — and a correction

One focused run failed with a **500** from `GET /products`. I did not wave it off:
looping the tests while forcing backend hot-reloads reproduced it, and an in-process
probe with exceptions raised captured the cause:

```
asyncpg.exceptions.DeadlockDetectedError: deadlock detected
Process A waits for AccessShareLock on relation …; blocked by process B.
Process B waits for AccessExclusiveLock on relation …; blocked by process A.
[SQL: SELECT p.id, … FROM public.products p …]
```

`startup_ddl()` runs `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (and `CREATE INDEX IF
NOT EXISTS`, backfill `UPDATE`s) on every boot; Postgres takes an ACCESS EXCLUSIVE
lock for the `ALTER` even when the column exists, so requests in flight during a
restart deadlock or block. → **B6.16** (`NEW-B54B-1`, P2). This is also the most likely
explanation of the one-off error recorded as "unexplained" in the F5.16 audit (both
happened right after an edit reloaded the dev container mid-test); that audit now says
so.

## What is NOT done / open

- B6.16 (above). `GET /products/{id}` still returns inactive products to anyone
  (FEATURES ۶.۱۸, pre-existing, not part of this task).
