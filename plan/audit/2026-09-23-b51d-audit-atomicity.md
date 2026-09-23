# Audit — B5.1d `record_audit` rolled back the mutation it audited (2026-09-23)

## Task

`B5.1d` (P2, Batch C), discovered during B2.1: on an insert failure,
`services/audit.py::record_audit` called `session.rollback()` and carried on. That
also discarded the order / refund / role / coupon / product / review change made
earlier on the same session; the router then committed an empty transaction and
answered **200 with the new values** — a silent lost update. Fifth task of the
back-to-back run.

## Spec check (Rule 0)

`[BE-04]` (audit trail of privileged mutations) — followed; the stale Supabase /
RLS wording ignored (Rule 0.2).

## Decision (the task asked for one, documented)

**All-or-nothing: a failed audit insert fails the request.** `record_audit` logs
and re-raises; FastAPI answers 500 and `get_session` rolls the whole transaction
back, so a privileged mutation and its entry land together or not at all. Chosen
over a SAVEPOINT (mutation commits, entry missing) because B5.1 states the rule
"an admin action without its audit trail, or vice versa, must not happen", and
B5.1b wants the trail to be trustworthy. Cost: if `audit_logs` itself is broken,
audited mutations fail until it is fixed — acceptable, since an audit insert only
fails when the database is in trouble. **Reversible** if the user prefers
availability over the guaranteed trail (swap to `begin_nested()`).

## Recon (Rule 6) / blast radius

18 call sites (`orders.py` ×5 incl. the customer cancel, `products.py` ×6,
`coupons.py` ×3, `reviews.py` ×2, `admin.py` role change, `notifications.py`
settings). Every one records the entry **before** its commit (checked), so
re-raising makes each of them atomic; none commits the mutation first. The only
`rollback()` next to an audit call (`reviews.py`) is on the 404 path, before it.

## What was done

`record_audit`: the `except` no longer rolls back and swallows — it logs
(`… failing the request`) and re-raises. Docstrings updated.

## Files changed

`backend/app/services/audit.py`, `backend/tests/test_audit_atomicity.py` (new);
docs: this audit, `plan/RULES.md`, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`,
`plan/session-log.md`, `plan/README.md`.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q tests/test_audit_atomicity.py   # 6 passed
```

## Verification results

The failure is **real, not mocked**: a temporary Postgres trigger rejects the
`audit_logs` insert for one specific entity id (dropped again in teardown; checked
that no `b51d_*` trigger/function remains).

| Check | Result |
|---|---|
| `tests/test_audit_atomicity.py` | **6 passed**: staff status change → 500, order unchanged; staff cancel → 500, status, **stock restore and the cancel notification** all rolled back; customer cancel → 500, unchanged; refund settlement → 500, refund still pending, order still paid, **no refund payment row**, no notification; coupon edit → 500, percent unchanged; control: the normal path → 200 with exactly one entry |
| **Negative control** (previous `audit.py`) | **5 failed, 1 passed** — the old code answered 200 with the change silently lost |
| full `pytest -q` | **157 passed** (151 + 6) |
| `ruff` / `api_smoke.py` | clean / **229 checks, 0 failed** |

**Verification level: integration tested** (live DB + in-process HTTP + smoke
against the running stack; no schema, infra or UI change).

## What is NOT done / open

- B5.1b (DB-level append-only audit table) is still open.
- The admin UI shows its generic error toast for the 500; no special copy for
  "audit unavailable".
