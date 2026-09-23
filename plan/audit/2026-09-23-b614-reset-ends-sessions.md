# Audit — B6.14 A password reset now ends existing sessions (2026-09-23)

## Task

`B6.14` (P2, Batch C), discovered during F2.3: access tokens are stateless HS256
JWTs valid for 7 days, so a token stolen before a password reset kept working
after it — the reset did not actually recover the account. First of the user's
"B6.14 then F5.16" run.

## Spec check (Rule 0)

`[BE-04]` (RBAC / security) — roles still come from `user_roles` on every
request, unchanged. Stack header (Supabase Auth) ignored — own JWTs are binding.

## Recon (Rules 6, 8, 9)

- Tokens are decoded only in `app/auth.py` (`get_current_user`,
  `get_optional_user`) — the one place to enforce the cutoff (R7). The only
  password-changing path is `services/password_reset.py::reset_password`.
- Contract: unchanged for valid tokens. A token issued before the account's last
  reset now gets **401** `نشست شما پایان یافته است؛ دوباره وارد شوید` on protected
  endpoints and is treated as **anonymous** on optional-auth ones (e.g. `/products`).
  The frontend already drops the stored token on 401 (F5.15), so the user lands on
  `/auth`.

## What was done

- `users.password_changed_at TIMESTAMPTZ` (additive, in `PASSWORD_RESET_DDL`);
  NULL on every existing row, so no current session is affected.
- `reset_password` stamps it (`now()`), in the same transaction as the new hash.
- `app/auth.py::_session_revoked()` — one PK lookup per authenticated request;
  both guards reject when `iat < floor(epoch(password_changed_at))`. A token
  without a usable `iat` cannot prove it is newer → rejected once a cutoff exists.
- Precision (documented in the code): `iat` is whole seconds, so the cutoff is too.
  The login right after a reset (same second) must work; the price is that a
  token issued in that same second **before** the reset survives. No-cutoff users
  (never reset) keep their sessions.

## Files changed

`backend/app/auth.py`, `backend/app/db.py`, `backend/app/services/password_reset.py`,
`backend/tests/test_session_revocation.py` (new), `backend/README.md`; docs: this
audit, `plan/RULES.md`, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`,
`plan/session-log.md`, `plan/README.md`.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q tests/test_session_revocation.py   # 6 passed
```

Browser: sign in on two browsers, reset the password in one; the other is sent to
`/auth` on its next page load.

## Verification results

| Check | Result |
|---|---|
| `tests/test_session_revocation.py` | **6 passed** — token older than the reset → 401 on `/auth/me`, `/orders`, `/notifications`; login right after the reset (same second) → 200; never-reset user with a 6-day-old token → 200; token without `iat` → 200 before, 401 after a reset; optional-auth: `/products` still 200 and `get_optional_user` returns `None` for the stale token, the fresh one resolves; staff token → `/admin/orders` 200 before, 401 after |
| **Negative control** (previous `auth.py`) | 4 failed (the revocation checks), 2 passed (the must-not-change checks) |
| full `pytest -q` | **163 passed** (157 + 6) — dev stack and clean stack |
| `ruff` / `api_smoke.py` | clean / **229 checks, 0 failed** (dev + clean) |
| Browser, two contexts ("laptop" signed in, "phone" resets through the UI) | **5/5** on the dev stack and on the warm clean stack: laptop opens `/account`; phone resets; laptop's next load → `/auth` and its token is dropped; phone signs in with the new password. (The first run right after the rebuild failed one 30 s text wait while the dev server compiled `/account` cold — the URL was already right; the warm rerun passed.) |
| Regression: F2.3 browser suite on the clean stack | **20/20** after a harness fix — its "same answer" check read response bodies inside an async handler and could lose one to the next navigation (the backend log shows both `/forgot` requests answered 202 even in the failing runs); it now awaits each response before moving on |
| Clean environment (`down -v && up -d --build`) | `db-init` exit 0, four stages; `/health` OK; `password_changed_at timestamptz` present, 0 rows stamped after seeding |

**Verification level: fully verified.**

## What is NOT done / open

- No "sign out everywhere" button or change-password endpoint (none existed); if
  one is added later it must stamp `password_changed_at` too.
- The same-second edge described above.
- Deleted-user tokens behave as before (no row → no cutoff; `/auth/me` answers 404).
