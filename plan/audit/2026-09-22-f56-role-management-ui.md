# F5.6 — Role management UI

**Date:** 2026-09-22 · **Task:** `F5.6` (P1, Batch B, `plan/frontend-tasks.md` /
`plan/MASTER-BACKLOG.md`; spec `[FE-08]` role-change trigger) · **Layer:**
frontend only

## Task

`PUT /admin/users/{id}/roles` (B5.4) existed and was audited, but `/admin/users`
was read-only: changing a staff role needed a raw API call. F5.6 adds a role-set
editor to the users page with a two-step confirmation, using the backend's
capability model as the authority.

## Spec check (Rule 0)

Followed:

* **[FE-08]** "role change trigger (promote/demote) behind a two-step security
  confirmation dialog": step 1 picks the role set, step 2 shows the diff and
  requires typing the target account's email.
* **[BE-04] security rule** — roles are only ever written through `user_roles`
  via the endpoint; the UI does not keep its own permission model.
* **B0.2 / B1.1** — semantic tokens; primary CTA `bg-terracotta text-white
  hover:bg-terracotta/90`. For the diff colours, spec B0.2's literal
  `emerald`/`rose` classes were **not** followed. `DESIGN_SYSTEM.md` §2.3 (repo
  wins, Rule 0.2) maps positive → `text-sage-deep` and negative →
  `text-destructive`, and forbids inline palette classes. The same correction was
  applied to the F5.5 audit-log error panel (`admin.audit.tsx`, committed in the
  F5.5 session with `rose-*`), which now uses `border-destructive/30
  bg-destructive/10 text-destructive`. `admin.refunds.tsx` and `admin.index.tsx`
  still use palette classes; that predates this work and was not touched.
* **B0.3** — modal title `font-serif`; email / id `font-mono`, LTR.
* **B0.4 / B0.5** — `rounded-xl` option cards with `border-border/60` and
  `hover:bg-muted/40`; Sonner toasts for success/failure.
* **B1.4 / B1.5 / B1.6** — Persian copy, logical spacing, verified at 375 px.
* **[FE-01].3** — direct URL entry by a role without the `users` capability
  still renders the existing Persian permission notice.

Deliberately not followed:

* **The rest of [FE-08]** (avatar, tier badge, order/address/wishlist tabs, LTV
  card) — that is `AB-FE-06` (Customer 360°), a separate backlog task.
* **"Promote to Admin"** wording — the legacy `admin` role cannot be set through
  `PUT /admin/users/{id}/roles` (the body accepts only `super_admin`,
  `order_manager`, `support`), so the top grant in the UI is «مدیر ارشد»
  (`super_admin`). Legacy `admin` / `customer` rows are shown read-only.
* **Spec stack header** (Supabase `has_role`, `SECURITY DEFINER`) — stale; the
  live repo is FastAPI + own JWT.

## Architecture check (Rules 6–10)

* **Owning module:** `src/routes/_authenticated/admin.users.tsx` (+ one method /
  one type in `src/lib/api.ts`).
* **Data flow:** users page → `api.adminSetUserRoles()` → `request()` →
  `backend/app/routers/admin.py::set_user_roles` → `public.user_roles` +
  `record_audit("update_user_roles")`. Backend unchanged.
* **Contract (unchanged):** `PUT /admin/users/{user_id}/roles`, body
  `{roles: ("super_admin"|"order_manager"|"support")[]}`. It is a **full
  replacement** of those three roles only: legacy `admin` and `customer` rows are
  left untouched. Response `{userId, roles}`. 401 anonymous, 403 without the
  `users` capability, 404 unknown user, 422 for any other role string. Guard
  `StaffUsers` = `{admin, super_admin}`, resolved from `user_roles` on every
  request (`resolve_roles`), so a stale JWT cannot keep or gain access.
* **Security (Rule 9):** the page lives behind the existing `users` tab, which
  the admin shell grants only to `admin` / `super_admin`, the same set as the
  endpoint. The UI sends only the three editable roles, so `admin` can never be
  sent from the client. The editor is disabled on the caller's own row (UX guard
  against self-lockout; see open items for the missing backend guard). The
  backend stays the authority: forced 403/500 responses keep the dialog open with
  an error toast and change nothing.
* **Repeat (Rule 10):** PUT with the same set is idempotent for `user_roles`
  (DELETE + `INSERT … ON CONFLICT DO NOTHING`). "Continue" is disabled until the
  set differs from the server state, and the confirm button is disabled while
  saving, so the UI does not send no-op or double PUTs. A no-op PUT sent directly
  to the API would still write an audit row; that is backend behaviour, left
  unchanged.
* **Cache:** success invalidates `["admin-users"]` (this list and the F5.5 staff
  filter `["admin-users","all"]`) and `["admin-audit-logs"]`.
* **Blast radius:** `api.ts` gains `StaffRole` + `adminSetUserRoles` (no existing
  member changed). `admin.users.tsx` is only consumed by the route tree. The
  `ROLE_LABELS` map is unchanged.

## What was done

1. `src/lib/api.ts` — `StaffRole` type; `api.adminSetUserRoles(userId, roles)`.
2. `src/routes/_authenticated/admin.users.tsx`:
   * a «نقش‌ها» button on every row, disabled (with a tooltip) on the signed-in
     admin's own row;
   * `RolesDialog` step 1: three checkbox cards (`super_admin`,
     `order_manager`, `support`), each with a one-line summary of what it
     unlocks (mirroring `ROLE_CAPABILITIES`); legacy roles listed read-only;
     «ادامه» only enabled when the set changed;
   * step 2: `+ افزودن` / `− حذف` diff, a note that the change applies on the
     user's next request and is audited, and a typed-email confirmation (case- and
     whitespace-insensitive, falls back to the user id if there is no email);
     «بازگشت» returns to step 1;
   * success toast + cache invalidation; the error toast distinguishes 403.

## Files changed

* `vogue-vintage-vibes/src/routes/_authenticated/admin.users.tsx`
* `vogue-vintage-vibes/src/lib/api.ts`
* `vogue-vintage-vibes/src/routes/_authenticated/admin.audit.tsx` (error-panel
  colour tokens only)
* `plan/audit/2026-09-22-f55-audit-log-viewer.md` (spec-check note for that fix)
* `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/backend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`, `plan/feature-roadmap.md`
* `vogue-vintage-vibes/FEATURES.md`, `vogue-vintage-vibes/DESIGN_SYSTEM.md`
* this audit

## Tests / verification (all executed in this session)

| Check | Result |
| --- | --- |
| `bunx tsc --noEmit` | clean |
| `bun run lint` | 0 errors, 15 pre-existing warnings (none in touched files) |
| `prettier --check` on touched files | clean |
| `bun run build` | OK |
| backend `pytest -q` against the live DB | 70 passed |
| `ruff check app tests` | clean |
| `tests/api_smoke.py` | 196 checks, 0 failed |
| Headless Chromium + direct API script | **40 checks, 0 failed** |

The script ran against the dev stack with the seeded accounts:

* **Backend authority:** anonymous PUT → 401; customer → 403; support → 403;
  order_manager trying to grant itself `super_admin` → 403; client-sent `admin`
  role → 422; unknown user → 404.
* **Page guards:** anonymous → `/auth?redirect=%2Fadmin%2Fusers`; customer,
  support and order_manager → permission notice and no role buttons.
* **Flow:** own row's button disabled; the dialog shows the legacy «مشتری» role as
  read-only; «ادامه» disabled with no change; cancel sends no request; reopening
  starts from server state; step 2 lists the diff and the email; confirm stays
  disabled for an empty or wrong email and is enabled for
  `Customer@sande.local ` (case and trailing space ignored); exactly one PUT with
  `{"roles":["support"]}`; toast; list shows the new chip.
* **Effect on existing JWTs:** the customer's *already-issued* token gets 200 on
  `/admin/contact-messages` after the grant and 403 again after the revoke.
* **Audit:** the grant writes `update_user_roles` with `old {roles: []}` →
  `new {roles: ["support"]}`.
* **Errors:** mocked 403 → «نقش شما اجازهٔ تغییر نقش کاربران را ندارد», mocked
  500 → server-error toast; the dialog stays open in both cases, and server state
  is unchanged afterwards.
* **Revoke:** the removal diff is shown, the PUT sends `{"roles":[]}` and the chip
  disappears.
* **Responsive:** 375 × 812 with the dialog open → no horizontal scroll; the
  support user's dialog pre-checks «پشتیبانی».
* **Cleanup:** after the run, every seeded account's roles are back to the seed
  state (customer `["customer"]`, support `["support"]`, admin still `admin`).
  Two `update_user_roles` audit rows per run remain in the dev DB.

After the token fix both browser scripts were re-run: F5.6 40/40, F5.5 35/35.
The F5.5 script's paging and diff assertions were made data-independent because
the dev audit log had grown to 75 rows. Walking to page 3 of exactly 75 rows
confirmed that «قدیمی‌تر» disables on an exact multiple of 25.

The first run had one failure (customer notice not found in time); a direct
probe showed the notice renders, so it was a dev-server first-compile delay.
The re-run was 40/40.
A visual check caught the dialog header running the name and email together
(`ms-2` on an LTR span). I moved the email to its own line and re-ran: 40/40.

## Verification level

**browser tested** (+ type/lint/build and backend regression suites). No infra/DB/
seed change, so no clean-environment run (Rule 14 n/a).

## What is NOT done / open

* **New `B5.4a` (discovered as `NEW-F56-1`, P2, backend):**
  `PUT /admin/users/{id}/roles` lets a caller demote themselves and remove the
  last `super_admin`. The UI blocks editing your own row, but that is UX only.
  If every account with the `users` capability loses it, nobody can manage roles
  without the DB. The backend should reject self-demotion and removal of the last
  holder of the `users` capability with 409. Recorded, not fixed (backend
  outside F5.6).
* **New `F5.10` (discovered as `NEW-F56-2`, P3, frontend):** a signed-in
  *customer* opening `/admin/*` sees the Persian "no admin access" notice, but the
  sidebar still lists the support tabs (داشبورد / پیام‌ها / نظرات). This comes
  from `ROLE_TAB_KEYS[role] ?? ROLE_TAB_KEYS["support"]` in `admin.tsx`. It is
  pre-existing and exposes no data (every call is gated), but the nav should be
  empty. Recorded, not fixed (Rule 12).
* The legacy `admin` role cannot be granted or removed from the UI (the endpoint
  does not accept it); that is by contract.
* The role summaries in the dialog copy the capability matrix by hand; if
  `ROLE_CAPABILITIES` changes, the hint text needs updating (the permission
  itself stays enforced by the backend).
* A demoted user who is currently signed in keeps the old *navigation* until
  their next `/auth/me` (page load). Every API call is blocked immediately.
* Out of scope and untouched: F5.9, AB-FE-02, AB-FE-05, F4.3, AB-FE-06.
* Docs untouched on purpose: `backend/README.md` (endpoint unchanged; its
  `PUT /admin/users/{id}/roles` row is accurate), `infra/README.md`,
  `vogue-vintage-vibes/README.md` (does not list admin screens), and the spec.
