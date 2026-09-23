# Audit — F5.15 A failed `/auth/me` signs the user out (2026-09-23)

## Task

`F5.15` (P2, Batch D), discovered during B2.1: `AuthProvider.refresh()` in
`src/lib/auth.tsx` called `setToken(null)` on **any** `api.me()` error, so a
network error, a backend restart or a 5xx signed a valid user out. Third task of
the back-to-back run.

## Spec check (Rule 0)

No spec section covers the client session; `B1` (Persian, no UI change) holds.
Stack header (Supabase auth) ignored — the repo's own JWT is binding.

## Recon / contract (Rules 6, 8, 9)

- Owning module: `src/lib/auth.tsx` (canonical frontend session, R7). Consumers
  of `refresh` (account profile save, and via `useAuth()` every component) keep
  the same signature `() => Promise<void>`.
- `GET /auth/me` answers: 200; **401** invalid/expired token (`get_current_user`);
  **404** profile/account gone; 403 is not returned today but also means "no
  session". Anything else (network error, aborted request, 5xx) says nothing about
  the token.
- Security: clearing on 401/403/404 is unchanged, so a revoked or garbage token is
  still dropped; the backend remains the only authority (every call is still
  re-checked server-side). `_authenticated`'s own `beforeLoad` (redirect to `/auth`
  on any `/auth/me` failure) is untouched — it never cleared the token, and the
  `/auth` page returns the user once the provider's retry succeeds.

## What was done

`refresh()` now:

- clears the token only for 401/403/404 (`ApiError.status`);
- otherwise keeps the token **and the current user**, stays `loading`, and retries
  after 1 s, 3 s and 10 s; after the last failure it stops (`loading` false) with
  the token still stored — the next page load tries again;
- `signIn` / `signUp` / `signOut` cancel a pending retry; the timer is cleared on
  unmount.

## Files changed

`vogue-vintage-vibes/src/lib/auth.tsx`; docs: this audit, `plan/RULES.md`,
`plan/frontend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`.

## How to verify

Browser, signed in: block `http://localhost:8000/auth/me` (devtools → 500 or
offline), reload → still signed in once it recovers, token kept; a garbage token in
`localStorage["sande.access_token"]` → signed out.

## Verification results

| Check | Result |
|---|---|
| Headless Chromium (16 checks) | **16/16**: quick successive page loads keep the token and `/account/notifications` + bell; mocked **500** on `/auth/me` actually served → token kept, no signed-in bell yet, then the retry signs the user back in **without a reload**; mocked **network failure** → token kept, retry recovers; garbage token (401) → cleared, signed out; deleted profile (404) → cleared; UI sign-in → `/account`; sign-out clears; no page errors |
| **Negative control** — same suite against the previous `auth.tsx` | **4 failed** (500 keeps token / retry recovers / network error keeps token / retry recovers) — the checks discriminate |
| Direct probe, old vs new code, mocked 500 | old: token gone right after the failed call; new: token kept, a second call retried |
| prettier / `tsc` / lint / build | clean / clean / 0 errors (15 pre-existing warnings) / OK |

Harness note: the first version of the suite passed against the *old* code too —
in dev mode `/auth/me` fires 2–3 s after load, so a fixed 2.5 s wait sometimes
checked before the request happened. The suite now waits until the mocked
endpoint was actually hit (asserted) before judging. The "quick successive loads"
check is a race and stays a regression smoke check only — it is not
discriminating.

**Verification level: browser tested** (frontend-only change; no backend/DB/infra).

## What is NOT done / open

- After three failed retries the UI shows signed-out until the next page load
  (the token is kept); no "connection lost" banner.
- `_authenticated`'s `beforeLoad` still redirects to `/auth` on a transient
  `/auth/me` failure (it recovers via the provider's retry); a gentler guard is not
  part of this task.
- F5.13 (hydration mismatch on the guest redirect) is separate and still open.
