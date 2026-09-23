# Audit — F5.20 Complete customer profile (2026-09-24)

## Task

`F5.20` (P1) — turn the minimal profile (`full_name` / `phone` / `avatar_url` /
email display on `/account`) into a structured, privacy-conscious customer
profile: personal info, contact verification state, optional Iranian national
ID, and an optional fashion size profile — full-stack, without touching
`AB-FE-06` (admin Customer 360°), banking data, or company billing.

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` before starting. The spec's profile module
(`[FE-0?]` account/profile section) asks for editable name/phone plus avatar and
order links; F5.20 is a superset requested by the user and adds the identity /
size-profile sections the spec does not describe. The spec's stale Supabase /
Lovable Cloud / `createServerFn` stack header was ignored as always — the live
repo is FastAPI + `src/lib/api.ts`. No spec section was contradicted; no Rule-4
status string or cart money rule was touched. Spec file itself not edited.

## Problem (what existed before)

- `profiles` carried only `full_name`, `phone`, `avatar_url` (+ `email` via
  `users`); `/account` showed three inputs and an avatar.
- `/auth/me` returned `UserInfoOut(full_name, phone, avatar_url, email, roles…)`;
  `PATCH /auth/me` updated those three fields.
- No first/last name, birth date, gender, national ID, verification state or
  size profile anywhere; no `email_verified_at` / `phone_verified_at`.
- `/admin/users` selects only `full_name, phone, avatar_url, created_at` — no
  leak risk from the new columns as long as that SELECT is not extended.

## Implementation

### Database (`backend/app/db.py`, `PROFILE_DDL`)

Idempotent startup DDL, per the repo's additive model (no migration framework):

- `ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_name/last_name (text)`,
  `birth_date (date)`, `gender (text)`, `national_id (text, UNIQUE where
  not null)`, `email_verified_at / phone_verified_at (timestamptz)`.
- New one-to-one table **`user_size_profiles`** — `user_id` is the primary key
  (FK → `users.id ON DELETE CASCADE`, exactly one row per user), `height`,
  `weight`, `chest`, `waist`, `hip` as INTEGER with CHECK ranges
  (height 100–250, weight 30–300, chest/waist/hip 40–200 cm/kg), `preferred_top_size`,
  `preferred_bottom_size`, `preferred_shoe_size`, `fit_preference` (text),
  `created_at` / `updated_at`.
- Existing rows are untouched (all columns nullable); a UNIQUE partial index on
  `profiles.national_id` (`WHERE national_id IS NOT NULL`) plus an
  application-level 409 guard because a Postgres UNIQUE violation would be a
  500 otherwise.

### Canonical helpers (`backend/app/services/profile.py`)

The one place the rules live (R7), called by both routers — validation is never
re-derived per route:

- `validate_national_id` — normalize (Persian/Arabic digits → ASCII, strip
  separators/ZWNJ, trim), accept **exactly 10 ASCII digits**, reject
  all-equal digits, enforce the Iranian national-ID checksum. Stored as TEXT so
  leading zeros survive; never an integer.
- `validate_birth_date` — real date, not in the future, not before 1900.
- `normalize_gender` — closed set `male / female / unspecified`.
- `validate_measurement` — unit ranges identical to the DB CHECKs.

### API contract (R8)

- `GET /auth/me` (existing) — `UserInfoOut` gains `first_name`, `last_name`,
  `birth_date`, `gender`, `national_id`, `email_verified_at`,
  `phone_verified_at`; `full_name`, `phone`, `avatar_url` unchanged for
  compatibility. `national_id` is returned **only here**, to the owner.
- `PATCH /auth/me` (existing) — accepts the new optional fields with the
  repo's clear semantics (**omitted = unchanged, explicit `null` = cleared**,
  implemented via Pydantic `model_fields_set` so `PATCH {}` cannot wipe the
  profile). `full_name` stays independently settable (back-compat); when
  `first_name` and/or `last_name` are sent and the request does not also set
  `full_name` explicitly, the server re-derives `full_name` from the merged
  result (new value COALESCE'd with the stored counterpart, `btrim`-ed), so
  checkout, the account header and the admin lists never show a stale name;
  clearing both names yields `""`.
- **New `GET/PATCH /auth/me/size-profile`** (`backend/app/routers/profile.py`,
  wired in `main.py`): account-scoped, `CurrentUser`-guarded, no user id in the
  path or body, so cross-user access is not expressible; PATCH creates the row
  on first use and follows the same clear semantics. Measurements must pass the
  same ranges as the DDL CHECKs. `GET` on a never-saved profile returns the
  all-null shape (204-like empty payload inside a 200 with all-null fields).
- Errors use the existing conventions (422 with a Persian `detail`,
  409 for a national-ID collision, 401/403 from the auth dependency); no stack
  traces or DB errors reach the client.

### Verification state — no fake verification

No OTP/email-verification flow exists in the repo (B2.1's providers are
unconfigured, B2.1a open). `email_verified_at` / `phone_verified_at` are
exposed and always NULL; **no code path in this task can set them**; entering a
phone/email does not mark anything verified. Real verification remains a
separate backlog item.

### National ID privacy (§11)

- Returned only by `GET /auth/me` to its owner. `/admin/users` list SELECT was
  not extended; admin user list API and UI show nothing new.
- Not in the JWT payload (tokens untouched, `TokenOut` unchanged), not in auth
  logs, not in audit logs (see below), not in the frontend global session
  object — the account page reads it from `api.me()` and never writes it
  anywhere else. Server request bodies are not logged.
- Self-service edit is not a privileged mutation, so no `audit_logs` record is
  written (consistent with the F2.3 decision: only privileged mutations are
  audited) — no second audit mechanism, nothing sensitive copied into audit JSON.

### Frontend (`src/lib/api.ts`, `src/routes/_authenticated/account.index.tsx`)

- `api.ts`: `UserInfo` extended; new `SizeProfile` type,
  `api.getSizeProfile()` / `api.updateSizeProfile()` — all HTTP through
  `src/lib/api.ts` (R7), no direct fetch.
- `/account` profile tab reorganized into the requested sections with the
  existing design system only (same `form.tsx` inputs, `ui/select.tsx`,
  existing card/section styling): «اطلاعات شخصی» (first/last name, birth date,
  gender), «اطلاعات تماس» (email read-only + تأیید state; phone + تأیید
  state), «اطلاعات هویتی» (national ID with a Persian 422-error surface),
  «سایز من» (height cm, weight kg, chest/waist/hip cm, preferred top/bottom/
  shoe size, fit preference).
- Save UX per §13: loading state, disabled submit while saving, success/error
  toast, **no optimistic writes** — the server response is canonical state;
  profile and size profile save independently so a size-profile failure never
  blocks the identity save.
- Birth date is a plain ISO `yyyy-mm-dd` `<input type="date">` (no second date
  library; the repo has no Jalali picker); gender is a closed-set select with
  «نامشخص» default; measurement inputs accept Persian digits and are
  range-checked in the UI as UX only — the backend remains authoritative.

## Security (R9)

- Ownership: both endpoints derive the user from the verified JWT
  (`get_current_user`); no client-supplied id is ever trusted. Cross-user
  access is structurally impossible on `/auth/me/*` (no id parameter exists).
- Anonymous: 401 from the auth dependency on all three endpoints.
- Roles come from `user_roles` as before; no role logic touched.
- Sensitive data exposure verified by tests and browser checks: `/admin/users`
  payload contains no `national_id`; the new fields reach only `/auth/me` (the
  network log in the browser suite confirms the only endpoints receiving
  profile data are `/auth/me` and `/auth/me/size-profile`).

## Tests (`backend/tests/test_profile.py`, 52 tests)

Existing profile compatibility, personal info save/clear/persist, national ID
(valid/checksum/leading zero/Persian digits/not exposed elsewhere), clear
semantics (omitted vs `null` vs `""`), verification state (never set), size
profile CRUD + range validation + cross-user, authorization (anonymous 401,
wrong-user impossible by construction), schema assertions (`information_schema`
+ `pg_indexes`).

Negative controls (§36), run once and reverted:

- replacing the `model_fields_set` clear semantics with the old
  `if x is not None` pattern → the omitted-field test fails;
- removing the size-profile ownership/user scoping → cross-user tests fail;
- removing the `user_id` primary key → the one-to-one uniqueness test fails.

## Verification (actual commands and results)

| Check | Result |
|---|---|
| Focused: `pytest -q tests/test_profile.py` | **57 passed** (live-DB on the docker stack; the pure part passed pre-stack, the live part skipped without DB) |
| Full: `./.venv/bin/python -m pytest -q` | **344 passed** (287 pre-existing + 57) |
| `./.venv/bin/python -m ruff check app tests` | clean |
| `./.venv/bin/python tests/api_smoke.py` | **253 routes/checks, 0 failed** (stack up) |
| Frontend `bunx tsc --noEmit` | 27 errors, **all pre-existing** (missing `@tanstack/react-table` types locally; confirmed by `git stash` A/B — my files contribute 0) |
| Frontend `bun run lint` | 0 errors / 16 warnings (warnings pre-existing; my files auto-fixed to 0) |
| Frontend `bun run build` | succeeds (vite build) |
| Clean environment `docker compose down -v && docker compose up -d --build` | `db-init` exit 0, four seed stages; `/health` OK |
| Schema proof on the fresh DB | `information_schema` shows all 8 new `profiles` columns + `user_size_profiles` with PK + CHECKs; `pg_indexes` shows the partial unique index |
| Seeded users on the fresh DB | `/auth/login` 200 for customer/admin; `/auth/me` returns the new null fields |
| Browser suite (`/tmp/f520-browser/f520-browser.js`, headless Chrome-for-Testing) | **24 checks, 0 failed** — guest redirect, sign-in via UI, sections render, email read-only + unverified badge, save toast, first/last/birth date/national ID persist across reload, invalid national ID → Persian 422 error and not stored, future birth date rejected, gender saved, size profile saves + persists (Persian digits), empty optional size fields allowed, no mobile horizontal overflow, `/admin/users` shows no `national_id`, national ID sent only to `/auth/me`, checkout reachable, account orders/notifications render, **zero page errors** — re-run green after the `full_name` derivation fix |
| `full_name` derivation in the browser | saving «سارا» / «محمدی» updates the account header to «سارا محمدی» and it persists after reload |
| Checkout regression | product page → size M → «افزودن به سبد خرید» → cart shows the line → `/checkout` loads with the address form; profile phone is **not** force-fed into `Address.phone` (§19 kept) |

Verification level: **clean-environment tested + browser tested**.

## Decisions

- **`full_name` compatibility (§4):** kept as a real column and still editable;
  when first/last are supplied the server derives it from the merged result
  (COALESCE with the stored counterpart) unless the request also carries an
  explicit `full_name`. One canonical value, no dual-source drift, all existing
  consumers (signup, checkout, admin lists) keep working. The first cut did not
  derive at all — the 5 new derivation tests caught it and it was fixed before
  commit.
- **Separate size-profile table (§6):** `user_size_profiles` with `user_id` as
  PK — one row per user, cascade delete, identity fields stay in `profiles`.
- **Optional national ID (§3):** never blocks anything; TEXT storage for
  leading zeros; 10-digit + checksum; only the owner sees it.
- **Verification timestamps (§10):** timestamps, not booleans; only a real
  future flow may set them; profile writes cannot.
- **Units (§7):** centimetres and kilograms, INTEGER + CHECK, documented in the
  service docstring and mirrored in the UI labels.
- **Date representation (§15):** canonical `date` in the DB; ISO input in the
  UI; Jalali display is a future enhancement (no second date library now).
- **Clear semantics:** omitted = unchanged, `null` = cleared — the repo's
  convention (F5.16), extended to the profile.
- **No audit rows for self-edits:** self-profile edits are not privileged
  mutations; consistent with existing policy, nothing sensitive enters
  `audit_logs`.

## Explicitly not done

- No card data / CVV / expiry / IBAN / Sheba / payout fields (§28).
- No company billing fields (§29).
- No admin Customer 360° (AB-FE-06 untouched) and no expansion of
  `/admin/users` (§21, §30).
- No automatic size recommendation (§18, §31).
- No Shahkar or any OTP/SMS/email-provider integration (§3, §10).
- No migration framework, no Supabase/RLS/RPC/`createServerFn`.

## Follow-ups (new, independent backlog items)

None discovered. Two known-adjacent items already exist and were **not**
duplicated: the real phone/email verification workflow (depends on B2.1a's
credentials) and the size-recommendation engine (needs a size-chart contract).
Both stay out of F5.20; the profile now stores exactly what they will consume.

Pre-existing doc glitch noticed while indexing (not fixed here, R12):
`plan/README.md` lists `2026-09-22-f25-pagination-everywhere.md` twice in the
audit index.
