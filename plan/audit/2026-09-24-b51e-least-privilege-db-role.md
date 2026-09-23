# Audit — B5.1e Run the backend as a least-privilege database role (2026-09-24)

## Task

`B5.1e` (P3, Batch C), discovered during B5.1b (`NEW-B51B-1`). The current execution
pointer of `plan/MASTER-BACKLOG.md` (§16).

The backend connected to Postgres as **the schema owner** — and, in the compose stack,
as the **superuser** `sande`. Any code path, or an injected query, could therefore
`ALTER`/`DROP` an object, `SET session_replication_role` to bypass the append-only
triggers (B5.1b for `audit_logs`, AB-BE-01 for `inventory_logs`), or rewrite the audit
trail. B5.1b recorded that "full proof needs a least-privilege app role" — this is it.

## Spec check (Rule 0)

- **`[BE-04]`** ("tamper-resistant trail of privileged mutations") and the spec's
  database/security sections: followed. The spec's Supabase/RLS wording is stale
  (Rule 0.2) — enforcement is plain Postgres roles + the existing triggers; no RLS,
  no second authz system.
- **`[BE-01]`/`[BE-03]`** flows (inventory ledger, refund settlement) are unchanged:
  every one of them is DML, which the app role keeps.
- No frozen status string, money rule or cart invariant is touched (Rule 4).

## Recon / contract (Rules 6–9)

- **Owning modules:** `backend/app/db.py` (engine + `startup_ddl()`), `infra/` (roles,
  compose env, start order), `backend/tests/conftest.py` (which role the suite uses).
- **Who runs DDL today (grepped):** `startup_ddl()` is called by `app/main.py` (boot),
  five `app/seed_*.py`, and ~25 test fixtures. `app/worker.py` runs none. The only DDL
  outside `db.py` is `services/recommendations.co_purchase_ddl()`, which
  `startup_ddl()` executes.
- **Data flow:** browser → FastAPI router → `services/*` → `SessionLocal` (the app
  role) → Postgres. The migrator connection is used **only** by `startup_ddl()`.
- **Canonical helpers (R7):** no new auth/role/data helper was added. The role split
  lives in `db.py` (`app_role_ddl()`), next to the DDL it belongs to; `startup_ddl()`
  stays the single bootstrap entry point.
- **Contract:** no API request/response shape changes at all — this is deployment +
  connection configuration. The only new operator-facing surface is configuration
  (`DATABASE_MIGRATOR_URL`, `DATABASE_APP_USER`, `DATABASE_APP_PASSWORD`) and the
  `tools` compose service.
- **Security (R9):** the app role is `NOSUPERUSER NOCREATEDB NOCREATEROLE`, does not
  own the database or any relation, has **no** `CREATE` on `schema public`, no
  `TRUNCATE`, and no DDL. `session_replication_role` (the trigger bypass) needs a
  superuser, so it is out of reach. The API container holds **only** the app-role
  credential: `DATABASE_MIGRATOR_URL`/`DATABASE_APP_USER` are set for the one-shot
  `db-init` job and the `tools` service, never for `backend`/`worker` (verified in the
  running container: both settings are empty there).

## What was done

**`app/db.py`**

- `engine` stays `DATABASE_URL` — the **DML-only app role** every router/service uses.
- New `migrator_engine` = `DATABASE_MIGRATOR_URL` (owner), **NullPool**: it exists for
  one-shot work, so no connection outlives the job's event loop (this also keeps the
  test suite's per-test loops clean). Falls back to `engine` when no separate owner URL
  is configured, so a single-role database behaves exactly as before.
- New `app_role_ddl(role, password)` — idempotent role creation
  (`DO $$ … IF NOT EXISTS (SELECT 1 FROM pg_roles …) … $$`, since `CREATE ROLE` has no
  `IF NOT EXISTS`), an `ALTER ROLE` that converges a rotated password, and the grants:
  `USAGE` on the schema (`CREATE` explicitly revoked), `SELECT/INSERT/UPDATE/DELETE` on
  all tables, `USAGE/SELECT` on all sequences, plus `ALTER DEFAULT PRIVILEGES` so
  objects the migrator creates later (startup DDL, seeds) are covered too. A role name
  cannot be a bind parameter, so it is validated against `^[a-z_][a-z0-9_]{0,62}$` and
  the password is quoted before interpolation.
- `startup_ddl()` now runs entirely as the migrator (enum autocommit connection, the
  guarded DDL transaction, the co-purchase refresh) and applies the role bootstrap after
  the tables exist. It runs **only** when `DATABASE_APP_USER` is set, i.e. the split is
  explicit.

**`app/main.py`** — the API no longer runs DDL at boot (the `lifespan` hook and its
`startup_ddl` import are gone), with a comment pointing at `db-init` and the compose
ordering. This also removes the last boot-time DDL from the request-serving process,
which is a bonus on top of B6.16's lock-free boot.

**`infra/docker-compose.yml`**

- The shared env anchor (`x-backend-env`) now carries the **app-role** `DATABASE_URL`;
  a second anchor (`x-migrator-env`) carries `DATABASE_MIGRATOR_URL`, the owner
  `DATABASE_URL` and the app-role credentials, and is used by `db-init` and by a new
  `tools` service (profile `tools`, so `up` never starts it).
- `backend` now depends on `db-init: service_completed_successfully` — the API no
  longer creates its own schema, so it must not start before the migration ran.
  (`worker` already depended on it.)

**`backend/tests/conftest.py`** — the suite now runs exactly like the stack:
`DATABASE_URL` = the app role, `DATABASE_MIGRATOR_URL` = the owner, and a collection-time
bootstrap applies `app_role_ddl()` (throwaway NullPool engine, disposed in the same
loop) so the app role exists before the first test connects as it. If there is no
database it prints one line to stderr instead of failing or looking green in silence
(the B6.13 trap).

**Tests updated for the split** (DDL needs the owner, and these three deliberately
create or drop objects): `test_catalog_errors.py` (fault-injection function/triggers),
`test_audit_atomicity.py` (forced audit-failure trigger), `test_variant_fields.py`
(replaying the SKU-index migration). The `TRUNCATE` assertions in
`test_audit_append_only.py` / `test_inventory_log.py` now accept either refusal — the
app role has no `TRUNCATE` privilege at all, so the ACL refuses before the trigger's
message is reached; the "row unchanged" assertions are untouched.

## Files changed

- `backend/app/db.py`, `backend/app/main.py`, `backend/app/config.py`,
  `backend/app/worker.py` (docstring)
- `backend/tests/conftest.py`, `backend/tests/test_db_least_privilege.py` (new),
  `backend/tests/test_catalog_errors.py`, `backend/tests/test_audit_atomicity.py`,
  `backend/tests/test_variant_fields.py`, `backend/tests/test_audit_append_only.py`,
  `backend/tests/test_inventory_log.py`
- `infra/docker-compose.yml`, `infra/.env.example`, `infra/README.md`
- docs: this audit, `backend/README.md`, `plan/RULES.md` (Rule 14 note),
  `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
  `plan/README.md`

## How to verify

```
cd backend
./.venv/bin/python -m pytest -q                 # 353 passed (5 new), as the app role
./.venv/bin/python -m ruff check app tests      # clean
./.venv/bin/python tests/api_smoke.py           # 257 checks, 0 failed, as the app role
```

**Clean environment (Rule 14)** — `docker compose down -v && docker compose up -d
--build`: `db-init` exit **0** with all four seed stages (`seed_auth`,
`seed_products`, `seed_demo`, `seed_coupons`), postgres + minio healthy,
`/health` → `{"ok":true,…}`, backend/worker/frontend up. `docker compose logs worker`
shows clean passes every 60 s.

**Live role proof** — the running API container:

```
API connection current_user: sande_app
  rolsuper: False | owns relations: 0
  upsert/deletes allowed: True            # SELECT/INSERT/UPDATE/DELETE on public.orders
  migrator URL in this container: '' | app user setting: ''
refused: ALTER TABLE public.products ADD COLUMN b51e_probe INTEGER
refused: DROP TABLE public.products
refused: CREATE TABLE public.b51e_probe (id int)
refused: TRUNCATE public.products
refused: ALTER TABLE public.audit_logs DISABLE TRIGGER ALL
refused: DROP TRIGGER audit_logs_no_update_delete ON public.audit_logs
refused: SET session_replication_role = 'replica'
```

**Negative control (Rule 13)** — the *same* seven statements through the same image as
the **owner** (`docker compose run --rm tools …`), inside one transaction that is rolled
back: all seven are **ALLOWED**, including `SET LOCAL session_replication_role =
'replica'` and dropping/recreating the audit trigger. So the refusals above are the
role, not the statements — and the old single-role setup is exactly that "owner" case.
The rollback left no trace (`information_schema` shows the probe column gone).

**Positive controls** — the whole API suite (353 tests) and the 257-check smoke run with
the app role, i.e. it can still do every DML the product needs: sign in, CRUD products
and variants, checkout (stock decrement + `inventory_logs` insert + `audit_logs` insert
on the same session), attach a fault trigger's effects, and delete a user — the last one
matters because the FK cascade needs `UPDATE (admin_id)` on the append-only
`audit_logs` (still permitted, and the trigger's one allowed change).

**Verification level: fully verified** — clean environment + live role proof + negative
control + the full suite and smoke as the app role.

## What is NOT done / open

- **`audit_logs` / `inventory_logs` keep table-level `UPDATE`/`DELETE`.** Append-only
  stays trigger-enforced (B5.1b) — what changes is that the app role can no longer
  disable or drop those triggers, which was the missing piece. A column-level ACL
  (`GRANT UPDATE (admin_id)`, `REVOKE UPDATE, DELETE`) would add a second line of
  defence but the FK's `ON DELETE SET NULL` needs that one column, and it would replace
  the tests' «append-only» signal with «permission denied». Recorded here as the
  residual, not silently dropped.
- **The migrator is the compose superuser `sande`** (which is also the schema owner).
  The task's "migrator role" is therefore the existing owner, not a new non-superuser
  role. A separate, non-superuser migrator role is possible but would mean re-owning
  every object; it adds no protection over "the API cannot use this credential".
- `plan/frontend-tasks.md`, `vogue-vintage-vibes/FEATURES.md`,
  `DESIGN_SYSTEM.md`, `plan/feature-roadmap.md`: untouched on purpose — no frontend
  code, component, token or user-visible capability changed (the API contract is
  identical).
- `plan/RULES.md` Rule 14's old note ("`db-init` and `backend` start in parallel") was
  updated: the API now waits for `db-init`, while the seeds still call `startup_ddl()`
  themselves so a standalone seed run keeps working.
