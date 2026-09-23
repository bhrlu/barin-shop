# Audit — B5.4a Role-change lockout guard (2026-09-23)

## Task

`B5.4a` (P2, Batch C, security), discovered during F5.6: `PUT /admin/users/{id}/roles`
let a caller remove their own users-capable role, and did not stop the last holder of
the `users` capability from being removed — after which roles can only be repaired in
SQL. The F5.6 UI disables your own row, which is not authorization.

## Spec check (Rule 0)

`[BE-04]` RBAC (roles only in `user_roles`, per-route capability) — followed.

## Recon / contract / security (Rules 6, 8, 9, 10)

- Capability map: `ROLE_CAPABILITIES["users"] = {admin, super_admin}`; the endpoint
  manages only `super_admin` / `order_manager` / `support`, so a target's legacy
  `admin` (and `customer`) rows survive any change.
- Only a caller holding `users` reaches the endpoint (`StaffUsers`), so "nobody holds
  it afterwards" can only happen through **self-demotion** or a **race** (two admins
  demoting each other at once, each counting the other before either commits) — which
  also covers a caller demoted between authorization and the change.
- Contract: unchanged on success; new **409** with a Persian `detail`:
  «نمی‌توانید دسترسی مدیریت کاربران را از حساب خودتان بردارید» /
  «دست‌کم یک حساب باید دسترسی مدیریت کاربران را نگه دارد». The F5.6 dialog already
  shows an `ApiError` message in its toast.

## What was done

- `services/roles.py::role_lockout_reason(is_self, target_roles_after,
  other_users_holders)` — pure decision, driven by `has_capability`, not hard-coded
  role names.
- `routers/admin.py::set_user_roles`: takes `pg_advisory_xact_lock('roles:users')`
  (the B3.11 pattern), computes the target's roles after the change (kept legacy rows
  ∪ new set) and the number of *other* users-capable accounts, and answers 409 when
  the decision refuses; otherwise unchanged (audit entry, response).

## Files changed

`backend/app/services/roles.py`, `backend/app/routers/admin.py`,
`backend/tests/test_role_lockout.py` (new), `backend/README.md`; docs: this audit,
`plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`.

## Verification results

| Check | Result |
|---|---|
| `tests/test_role_lockout.py` | **9 passed** — pure: self losing `users` → refused; self keeping it (super_admin, or a legacy `admin` row) → allowed; last holder removed → refused; one of several → allowed. Live HTTP: super_admin demoting themselves (to none / to support) → 409, roles unchanged; self change keeping super_admin → 200; legacy admin dropping own super_admin → 200 (keeps `admin`); demoting another holder → 200; a caller demoted meanwhile → 403 |
| **Negative control** (previous endpoint) | the self-demotion test fails (the old code answered 200); the others are pure or must-stay-allowed checks |
| full `pytest -q` / `ruff` / `api_smoke.py` | **179 passed** / clean / **229 checks, 0 failed** (incl. the existing role grant/demote flow) |

The "no holder left" branch is pinned by the pure tests only: the dev database always
keeps the seeded legacy `admin`, and emptying the role table in a live test would risk
the shared database.

**Verification level: integration tested.**

## What is NOT done / open

- No UI change (none needed); the race path is covered by the lock + the decision, not
  by a concurrent-request test.
