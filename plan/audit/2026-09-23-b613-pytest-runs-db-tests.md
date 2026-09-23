# Audit — B6.13 The documented `pytest -q` silently skipped every live-DB test (2026-09-23)

## Task

`B6.13` (P2, Batch C), discovered during B2.1: `cd backend && ./.venv/bin/python -m
pytest -q` — the verification command in `AGENTS.md` and Rule 13 — reported green
while skipping every live-database test. Fourth task of the back-to-back run.

## Spec check (Rule 0)

Not covered by the spec (test harness). Nothing ignored.

## Root cause

`app.config.settings` is built once, at the first `import app…`, and cached. Four
unit-test modules (`test_addresses.py`, `test_availability_and_filters.py`,
`test_pricing_and_coupons.py`, `test_variants.py`) did
`os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")`
at import. `test_addresses.py` is collected first, so the dummy URL won, and every
live-DB module's `_db_available()` then answered "no database reachable" → skip.

## What was done

- New `backend/tests/conftest.py`: the single test-session default —
  `DATABASE_URL` = the local compose Postgres, `JWT_SECRET` = `test-secret` —
  via `setdefault`, so an exported value still wins. pytest imports it before any
  test module.
- The four dummy-URL lines removed (the other modules' compose-URL `setdefault`
  lines are now no-ops; left untouched — minimal diff).
- `backend/README.md` test section corrected (the "export DATABASE_URL" workaround
  note from B2.1 is gone).

## Files changed

`backend/tests/conftest.py` (new), `backend/tests/test_addresses.py`,
`backend/tests/test_availability_and_filters.py`,
`backend/tests/test_pricing_and_coupons.py`, `backend/tests/test_variants.py`,
`backend/README.md`; docs: this audit, `plan/backend-tasks.md`,
`plan/MASTER-BACKLOG.md`, `plan/session-log.md`, `plan/README.md`.

## How to verify

```bash
cd backend
env -u DATABASE_URL ./.venv/bin/python -m pytest -q      # stack up   → 151 passed
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5999/postgres \
  ./.venv/bin/python -m pytest -q                        # nothing on it → DB tests skip
```

## Verification results

| Run | Before (same tree, changes stashed) | After |
|---|---|---|
| documented command, no env vars, stack up | **79 passed, 72 skipped** | **151 passed, 0 skipped** |
| `DATABASE_URL` pointing at a closed port | — | 79 passed, 72 skipped, reason «no database reachable» (clean skip, no errors) |
| `ruff check app tests` | — | clean |

**Verification level: locally tested** (test-harness change; no app code, API,
DB or infra touched).

## What is NOT done / open

- The redundant per-module `setdefault` lines in the live-DB modules stay (no-ops).
- No CI workflow exists in the repo; nothing to update there.
- Earlier audits that say "run with `DATABASE_URL` exported" are historical and
  were left as written.
