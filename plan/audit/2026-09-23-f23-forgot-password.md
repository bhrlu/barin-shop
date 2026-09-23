# Audit — F2.3 Forgot password (2026-09-23)

## Task

`F2.3` (P1, Batch F) from `plan/MASTER-BACKLOG.md`: reset-token generation,
secure storage, expiry, one-time use, safe user-enumeration behaviour, reset
email, reset endpoint, request UI, reset UI. Second task of the user's
back-to-back run. Dependency `B2.1` (notification transport) was DONE.

**Decision taken without the user (stop-condition check, §18).** SMTP is not
configured (B2.1a), so a real reset email cannot be delivered. I did **not** add
any dev shortcut that exposes the link (logging it, returning it from the API):
that would be a standing account-takeover path if it ever reached production. The
reset email goes through the canonical notification service and is simply not sent
while email is off/unconfigured; tests use a stub provider, and the browser test
creates its link as a DB fixture (hash only, like the app). To see real reset
emails locally, point `SMTP_*` at a mail catcher (e.g. Mailpit) and switch email on.

## Spec check (Rule 0)

- The spec has no password-reset module; Part B `B0`/`B1` (Persian, RTL,
  tokens, mobile-first) and `B5` (head(), states) applied to the two new pages.
- Part A stack header (Supabase Auth reset emails / `createServerFn`) — ignored,
  stale (Rule 0.2); the repo's own JWT auth is binding.
- `[BE-04]` audit logging is for staff mutations; a customer's own reset is not
  audited (not a privileged mutation).

## Recon (Rule 6)

- Owning modules: `routers/auth.py` (auth endpoints), `security.py`
  (`hash_password`), new `services/password_reset.py`, `services/notifications.py`
  (the only email path, R7), DDL in `db.py`; frontend `src/lib/api.ts`,
  `routes/auth.tsx`, new `routes/forgot-password.tsx` / `reset-password.tsx`.
- Password policy reused from `SignUpRequest` (6–128 chars; bcrypt truncates at
  72 bytes identically on hash and verify).
- Existing tests touching auth: login/signup in `api_smoke.py`.

## Contract (Rule 8)

| Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|
| `POST /auth/password/forgot` | – | `{email}` (5–120 chars) | **202** `{ok: true, message}` — identical for unknown, known and throttled addresses | 422 malformed body |
| `POST /auth/password/reset` | – | `{token (20–200), password (6–128)}` | 200 `{ok: true}` | 400 `لینک بازیابی نامعتبر است یا منقضی شده است…` (unknown / used / superseded / expired); 422 malformed |

## Security (Rule 9) and repeats (Rule 10)

- **Enumeration:** same status and body for every address; the email lookup is
  case-insensitive. (A timing difference between the known and unknown paths —
  a few DB statements — remains; not mitigated.)
- **Storage:** `password_reset_tokens.token_hash` = SHA-256 of
  `secrets.token_urlsafe(32)`; the raw token never touches the DB (test dumps the
  row as JSON and asserts it is absent) and never goes to the outbox.
- **One-time:** `SELECT … FOR UPDATE` on the unused, unexpired row, then every
  outstanding row of the user is marked `used_at` in the same transaction — a
  second use (or a concurrent one) finds nothing → 400.
- **Supersession:** a new request spends all earlier unused links.
- **Expiry:** `PASSWORD_RESET_TTL_MINUTES` (30).
- **Mail-bombing:** at most `PASSWORD_RESET_MAX_PER_HOUR` (3) links per account
  per hour; over the cap the API answers identically and sends nothing.
- **Channel rule (B2.1):** sent only when the admin email switch is on AND SMTP is
  configured, after COMMIT (a rolled-back request sends nothing); a provider error
  is logged (never the body) and never fails the request.
- **Not done:** existing sessions survive a reset (stateless 7-day JWTs) →
  recorded as **B6.14**.

## What was done

Backend: `password_reset_tokens` DDL; `services/password_reset.py`
(`request_reset`, `reset_password`, `hash_token`, email text); two endpoints in
`routers/auth.py`; `notifications.queue_private_email()` — the email-only,
not-persisted entry point F2.3 needed (after-commit hook extended, rollback clears
it); config + compose + `.env.example` for the two knobs; smoke checks.

Frontend: `api.forgotPassword` / `api.resetPassword`; «رمز عبور را فراموش
کرده‌اید؟» on `/auth` (sign-in mode); `/forgot-password` (form → the server's
neutral message, error state); `/reset-password` (`validateSearch` drops a
malformed token as `undefined`; missing/malformed → notice + «درخواست لینک
تازه»; client checks length and confirmation before any request; 400 → Persian
error + new-link link; success → «ورود به حساب»); a line on `/admin/settings`
that the reset email uses the email channel.

## Files changed

Backend: `app/services/password_reset.py` (new), `app/services/notifications.py`,
`app/routers/auth.py`, `app/schemas.py`, `app/db.py`, `app/config.py`,
`tests/test_password_reset.py` (new), `tests/api_smoke.py`, `.env.example`,
`README.md`. Frontend: `src/routes/forgot-password.tsx` (new),
`src/routes/reset-password.tsx` (new), `src/routes/auth.tsx`, `src/lib/api.ts`,
`src/routes/_authenticated/admin.settings.tsx`, `src/routeTree.gen.ts`
(generated), `FEATURES.md`. Infra: `infra/docker-compose.yml`, `infra/.env.example`,
`infra/README.md`. Docs: `plan/RULES.md`, `plan/MASTER-BACKLOG.md`,
`plan/frontend-tasks.md`, `plan/backend-tasks.md`, `plan/feature-roadmap.md`,
`plan/session-log.md`, `plan/README.md`, this audit.

## How to verify

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres JWT_SECRET=test-secret \
  ./.venv/bin/python -m pytest -q tests/test_password_reset.py        # 14 passed
curl -s -X POST localhost:8000/auth/password/forgot -H 'content-type: application/json' \
  -d '{"email":"nobody@example.com"}'                                  # 202, neutral message
```

Browser: `/auth` → «رمز عبور را فراموش کرده‌اید؟» → submit → neutral message.

## Verification results

| Check | Result |
|---|---|
| `tests/test_password_reset.py` | **14 passed** — identical answers (unknown/known, case-insensitive), hash-only storage + nothing in the outbox, 422s, reset once then 400, expired → 400, newer link supersedes, bad token/short password, throttle (identical answers, capped emails/rows), email switch off, SMTP unconfigured, provider failure → still 202, rollback → no email and no token |
| Mutation checks | one-time use removed → 2 fail; throttle removed → 1 fail; unknown user made distinguishable → 1 fail (all restored) |
| full `pytest -q` (DB exported) | **151 passed** (137 + 14) — dev stack and clean stack |
| `ruff` / `api_smoke.py` | clean / **229 checks, 0 failed** (dev + clean) incl. identical 202s and bad token → 400 |
| frontend prettier / `tsc` / lint / build | clean / clean / 0 errors (15 pre-existing warnings) / OK |
| Headless Chromium (20 checks) | **20/20** on the dev stack and again on the clean stack: `/auth` link; known vs unknown → byte-identical 202 bodies; success panel; missing and malformed token → notice; unknown token → Persian 400 + new-link link; short password and mismatch → Persian client errors with no request sent; valid link → success, token spent in the DB, **UI login with the new password lands on `/account`**, old password → 401; reused link → 400; mobile 390 px no horizontal scroll (both pages); admin settings shows the channel note; no page errors; no 5xx |
| Clean environment (`down -v && up -d --build`) | `db-init` exit 0 through all four stages; `/health` OK; table + 4 indexes on the fresh DB; both env vars in the container |

Harness notes (not app defects): the first run clicked before hydration (native
form submit) — the test now waits for React's fiber on `<form>`; the second run's
"valid link" failure was the app **correctly** superseding the fixture link after
the test's own forgot request — the fixture is now issued afterwards.

**Verification level: fully verified** — except real email delivery (SMTP not
configured, B2.1a), which was exercised only through a stub provider.

## Discovered (recorded, not fixed)

- **B6.14** (`NEW-F23-1`, P2) — a password reset does not end existing
  sessions: JWTs are stateless for 7 days, so a stolen token outlives the reset.
  Needs a per-user `password_changed_at` (or token version) checked in
  `get_current_user`.

## What is NOT done / open

- Real reset-email delivery (B2.1a); no mail catcher added to compose.
- Session revocation (B6.14); no "password changed" confirmation email.
- No per-IP limit on `/auth/password/forgot` (the per-account cap covers
  mail-bombing; enumeration is prevented by identical answers, not by rate).
- `DESIGN_SYSTEM.md` untouched — the pages reuse the `/auth` form pattern with no
  new component or token.
