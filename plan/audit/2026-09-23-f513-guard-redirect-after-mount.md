# Audit — F5.13 Guest direct-load of a protected route logs a hydration mismatch (2026-09-23)

## Task

`F5.13` (P3, Batch D), discovered during B2.1: opening an `_authenticated` route
signed out (e.g. `/account/payments`) logged «Hydration failed because the server
rendered HTML didn't match the client». Last task of the back-to-back run.

## Spec check (Rule 0)

`[FE-01]`.3 (auth guard with a Persian permission redirect) — behaviour kept: guests
still land on `/auth` with the target in `?redirect=`. B2 routing conventions
(TanStack file routes, no react-router) followed. Stack header ignored (Rule 0.2).

## Root cause

`_authenticated/route.tsx` is `ssr: false`: the server renders the root shell and a
placeholder for the route. Its `beforeLoad` threw `redirect()` for a guest. On a
**direct page load** that throw happens during the first client pass, so the router
swapped the matched tree to `/auth` (an SSR route whose markup is not in the HTML)
while React was hydrating the server HTML → mismatch → React discards and
re-renders the tree. Signed-in loads (no redirect) never mismatched.

## What was done

`beforeLoad` no longer throws: it resolves `{ user }` (`null` without a token or
when `/auth/me` fails). The route's layout renders nothing without a user and
navigates **once**, from an effect, to `/auth?redirect=<the URL first rendered>`
(`replace`). The URL is captured on first render because, while the navigation is
in flight, `useLocation()` already reports `/auth` — my first attempt used
`<Navigate>`, which re-fired with `/auth?redirect=/auth…` in an endless loop (caught
by the test below before anything was committed). The rule is now in
`DESIGN_SYSTEM.md` §4.

Security: unchanged — no child route has its own `beforeLoad`/`loader`, the layout
renders no `<Outlet />` (so no child component or query runs) without a user, and
every API call is still authorized server-side. `/auth` keeps honouring
`?redirect=`.

## Files changed

`vogue-vintage-vibes/src/routes/_authenticated/route.tsx`,
`vogue-vintage-vibes/DESIGN_SYSTEM.md`; docs: this audit,
`plan/frontend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
`plan/README.md`.

## How to verify

Signed out, open `http://localhost:5173/account/payments` directly with devtools →
you land on `/auth?redirect=/account/payments`, and the console shows no hydration
error.

## Verification results

| Check | Result |
|---|---|
| **Baseline** (previous guard), headless Chromium, 20 checks | **7 failed** — every guest direct load (`/account`, `/account/orders`, `/account/payments`, `/account/notifications`, `/admin`, `/admin/settings`, `/payment/<id>`) logged «Hydration failed» |
| First fix attempt (`<Navigate>`) | 14 failed — redirect loop (`?redirect=/auth?redirect=…`) and «Maximum update depth exceeded»; replaced before commit |
| **Final**, same 20 checks | **20/20**: all 7 guest direct loads → `/auth?redirect=<exact path>` with no hydration error; signed-in customer stays on `/account` and `/account/orders` with no error; invalid token → `/auth`; guest clicking «حساب کاربری» (client navigation) → `/auth` |
| Regression: B2.1 notification suite | **58/58** (account + admin pages, direct URLs, refresh, role gating) |
| Regression: F5.15 auth-session suite | **16/16** |
| Regression: role/route sweep (54 checks) | **54/54** — every admin route × admin / order_manager / support with unchanged tab gating, storefront + account routes as customer and guest, bell presence, coupon Switch toggle + RTL geometry; **0 hydration mismatches** recorded (the previous sweep counted 3). An intermediate run failed its coupon step because it clicked `.first()` and the list reorders after a toggle — a harness bug that flipped both seed coupons inactive on the dev DB; they were restored to their seeded `active = true` and the step now locates the card by code and verifies the restore through the API |
| prettier / `tsc` / lint / build | clean / clean / 0 errors (15 pre-existing warnings) / OK |

**Verification level: browser tested** (frontend-only; no backend/DB/infra).

## What is NOT done / open

- While `/auth/me` is in flight on a direct load, the protected area shows nothing
  (as before — the route was not server-rendered either way); no skeleton added.
