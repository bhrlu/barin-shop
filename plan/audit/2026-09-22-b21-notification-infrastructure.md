# Audit — B2.1 Notification infrastructure (2026-09-22)

## Task

`B2.1` from `plan/MASTER-BACKLOG.md` (P1, Batch F), executed with the user's
explicit product adjustment of 2026-09-22:

- no real Kavenegar or SMTP credentials exist — do not invent them, do not claim
  delivery, do not make business flows depend on unavailable providers;
- build the **internal (in-app) notification system** as a production feature;
- build the **SMS/email provider layer** ready for real credentials later;
- let admins switch SMS and email on/off independently; the switches must never
  affect internal notifications;
- business logic depends on one canonical notification service.

Not in scope (and not done): F2.3 forgot-password, B2.5 job queue/worker, B4.13
preorder, F5.9, any other admin work.

## Spec check (Rule 0)

| Spec section | Used? | Note |
|---|---|---|
| Part A `[BE-07]` SMS notification gateway | **followed in part** | Customer triggers (processing/paid, shipped with tracking number, refund approved/settled) are covered, plus order created / cancelled from decision D2. The "immediate alert to the operations team on high-value orders or new refund claims" is **deliberately not built**: D2 limits this backlog to customer transactional notifications. |
| Part A `[BE-05]` order lifecycle | followed | Notifications fire at the existing state-machine points; no status string or transition changed. |
| Part A `[BE-04]` RBAC + audit | followed | New `settings` capability (admin/super_admin), switch changes audited. |
| Part A stack header / A2 `createServerFn` / Supabase | **ignored** | Stale stack; FastAPI + `src/lib/api.ts` is binding (Rule 0.2). |
| Part A3 webhooks under `src/routes/api/public/*` | ignored | No webhook here; B2.5 owns webhooks/jobs. |
| B0.2/B0.3/B0.4 colours, type, radii | followed via DESIGN_SYSTEM §2.3 | Tone recipes (sage/gold/sand), `rounded-2xl` cards, `shadow-sm`/`shadow-lg`; the B0.2 `emerald/amber` classes are not used (B1.1 + DESIGN_SYSTEM §2.3 win). |
| B1 invariants | followed | Persian copy, Persian digits (`toFa`, backend `fa()`), RTL, mobile-first; no hard-coded colours. |
| B2 directory layout | followed | `routes/_authenticated/account.notifications.tsx`, `admin.settings.tsx`, `components/NotificationBell.tsx`. |
| `[FE-01]` admin shell | followed | New «تنظیمات» nav item with the canonical active style; role-gated. The spec's topbar has no bell — the storefront header (rendered on every route) carries it. |
| B4.1 formatting, B4.3 skeleton/empty | followed | `formatToman` format mirrored in the backend (`toman()`), clay skeletons, dashed empty states. |
| B5 pre-flight checklist | followed | RTL, Persian, skeleton + empty states, admin guard, `head()` per new route. |
| Part C #8 "SMS notifications — Pending" | **out of date** | Now: in-app done, SMS/email infrastructure done but inactive (B2.1a). The spec is the user's document and was not edited. |

## Reconnaissance (Rule 6)

1. **Owning modules.** Backend: new `services/notifications.py` (+
   `services/notification_providers.py`), new `routers/notifications.py`, DDL in
   `db.py`; hooks in `services/checkout.py`, `services/payments.py`,
   `services/order_lifecycle.py`, `routers/orders.py`. Frontend: `src/lib/api.ts`,
   new `src/lib/notifications.ts`, `components/NotificationBell.tsx`,
   `SiteHeader.tsx`, `routes/_authenticated/{account,admin}.*`.
2. **Data flow.** Business event (checkout / payment verify / simulator /
   staff PATCH / cancel / refund resolve) → `notify_order_event` /
   `notify_refund_event` → `notifications` (+ `notification_deliveries`) on the same
   session → commit → after-commit dispatch → provider. UI: bell/page →
   `api.notifications*` → `routers/notifications.py` → Postgres.
3. **Contract.** See "Contract" below.
4. **Auth.** Inbox: `CurrentUser`, every query scoped `user_id = caller` in SQL.
   Switches: new `StaffSettings` = `require_staff("settings")`, capability mapped to
   `{admin, super_admin}` in `ROLE_CAPABILITIES` (roles from `user_roles`, never the
   token claim).
5. **Existing tests.** No notification tests existed; the lifecycle suites
   (`test_order_lifecycle_stock.py`, `test_refund_requests.py`,
   `test_coupon_cap_integration.py`) and `api_smoke.py` cover the flows the hooks
   sit in — all still green.
6. **Docs.** D2 in the Master Backlog, `backend-tasks.md` B2.1, spec `[BE-07]`,
   B3.11 / B6.8 / B6.9 audits (transaction and dedup patterns).
7. **Existing pattern / prior art.** No notification, settings or feature-flag
   primitive existed anywhere (`grep` for notification / settings / feature flag
   tables and modules: none). Patterns reused: idempotent DDL lists in `db.py`,
   `record_audit`, `pagination.envelope`/`count_rows`, capability guards,
   `request()`/`Page<T>` in `api.ts`, the `useFavorites` hook shape, `Pager`,
   `StatusBadge` tone recipes, the admin card-list pages.

Blast radius checked before editing shared code: `ROLE_CAPABILITIES` (only
`has_capability` + `require_staff`; adding a key changes nothing else),
`audit.ACTIONS`/`_ENTITY_TYPES` (vocabulary only; the F5.5 viewer got labels),
`SiteHeader` (rendered once by `__root.tsx` on every route — which is why the
admin shell must **not** get a second bell), `ui/switch.tsx` (consumers:
`admin.coupons.tsx` + the new settings page), `api.ts` (additive only).

## Contract (Rule 8)

| Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|
| `GET /notifications` | user | `page` ≥1 (default 1), `page_size` 1–100 (default 20), `unread` bool | 200 `{items, total, page, page_size, pages}` — **always** the envelope (a new endpoint has no legacy bare-list callers); items `{id, type, title, message, data, read_at, created_at}` newest first | 401; 422 bad query |
| `GET /notifications/unread-count` | user | — | 200 `{unread}` | 401 |
| `PATCH /notifications/{id}/read` | user | — | 200 item; idempotent (first `read_at` kept) | 401; 404 `اعلان پیدا نشد` for missing **or someone else's**; 422 non-UUID |
| `POST /notifications/read-all` | user | — | 200 `{updated}` | 401 |
| `GET /admin/settings/notifications` | admin/super_admin | — | 200 `{internal_enabled: true, sms_enabled, sms_provider, sms_configured, sms_active, email_*, updated_at, updated_by}` | 401; 403 |
| `PATCH /admin/settings/notifications` | admin/super_admin | `{sms_enabled?, email_enabled?}` — strict booleans, extra keys forbidden | 200 same shape; audited | 400 empty; 422 non-bool / unknown key (e.g. `internal_enabled`); 401; 403 |

Error bodies are FastAPI's `detail` (string), which `request()` already unwraps.
No existing response shape changed.

## Security (Rule 9)

- Anonymous → 401 on all six endpoints; invalid JWT → 401.
- A customer can only read/mark their own rows: ownership is in every `WHERE`;
  another user's id is indistinguishable from a missing one (404).
- Switches: customer, `support`, `order_manager` → 403 (API) and the Persian
  permission notice (UI, including direct URL entry); admin and super_admin → 200.
- No client-supplied user id, role, recipient or message text reaches the
  service — recipients come from `users.email` / `profiles.phone` / the order's
  shipping phone in SQL.
- Provider secrets: environment only; `ProviderError` messages never contain the
  Kavenegar key (it sits in the URL path — `httpx` errors are reduced to their
  class name) or the SMTP password (tests assert both).

## State machine / repeats (Rule 10)

"What if this runs twice?" — answered by one mechanism, `UNIQUE (user_id,
event_key)`:

| Event | Key | Repeat behaviour |
|---|---|---|
| order created | `order:<id>:created` | a second call inserts nothing |
| payment confirmed | `order:<id>:paid` | gateway verify, repeat callback/verify (`already_paid`), simulator repeat and a staff `payment_status=paid` all converge on one row |
| shipped | `order:<id>:shipped` | fires only when the PATCH actually changed the status to `shipped`; a no-op repeat or a later tracking-code edit adds nothing |
| cancelled | `order:<id>:cancelled` | fires inside `cancel_order_tx` (both cancel paths); a repeat cancel is already a no-op/409 there |
| refund approved | `refund:<id>:approved` | approve ×2 → one |
| refund settled | `refund:<id>:settled` | settlement is terminal (409 on repeat, unchanged) |

External sends ride on the same key: outbox rows are created only next to a
**new** inbox row, and `UNIQUE (notification_id, channel)` caps them at one per
channel. `dispatch_deliveries` picks only `pending`/`failed` rows under
`FOR UPDATE … SKIP LOCKED`, so a retry never re-sends a `sent` row. No status
string, transition or terminal state changed.

## Money and stock (Rule 11)

No price, total, coupon, stock or refund-amount logic changed. The hooks are
additive inserts at the end of the existing transactions. The invariant that
matters here — *a notification and its business change commit or roll back
together* — is covered by tests (failed checkout leaves none; an explicit
rollback discards the row and its outbox; a failing provider leaves the order
`pending/unpaid` exactly as checkout made it).

## What was done

### Architecture

```text
business event (existing lifecycle point, existing session/transaction)
        │  notify_order_event / notify_refund_event  → notify()
        ▼
notifications            ← INSERT … ON CONFLICT (user_id, event_key) DO NOTHING
        │ (only for a NEW row, per channel the admin switched on)
        ▼
notification_deliveries  ← pending | skipped(provider_not_configured | no_recipient)
        │ SQLAlchemy after_commit (outer transaction only; rollback drops the queue)
        ▼
dispatch_deliveries()    ← background task, own session, row lock, ≤2 concurrent
        ├── SmsChannel   → KavenegarSmsProvider   (KAVENEGAR_API_KEY / _SENDER)
        └── EmailChannel → SmtpEmailProvider      (SMTP_HOST / _PORT / … / _FROM)
            result: sent | failed(last_error) | skipped(channel_disabled | provider_not_configured)
```

- **Internal channel** = the `notifications` row; always on, no switch.
- **Why after-commit and not inline:** sending inside the transaction would hold
  row locks during a network call and could send a message for an order that then
  rolls back. The outbox + after-commit hook gives "no message without a committed
  event" and "a failing provider never touches the event". It is not a job queue:
  if the process dies between commit and send, the row stays `pending` for the
  B2.5 sweeper.
- A SAVEPOINT release also fires SQLAlchemy's `after_commit`; the hook ignores it
  (`in_nested_transaction()`), so nothing is sent before the outer COMMIT.
- A notification insert error is **not** swallowed: it fails the business request,
  keeping the two atomic (the user's rule: never one without the other).

### Business events connected

| Event | Where the hook sits |
|---|---|
| order created | `services/checkout.py::create_order` (end of the checkout transaction) |
| payment confirmed | `services/payments.py::verify_and_finalize` (gateway / manual verify); `routers/orders.py::payment_complete` (simulator, success only); `routers/orders.py::patch_order` when `payment_status` changes to `paid` |
| order shipped | `routers/orders.py::patch_order` when `status` changes to `shipped` (message carries the tracking code set in the same PATCH) |
| order cancelled | `services/order_lifecycle.py::cancel_order_tx` — both the customer `POST /cancel` and the staff PATCH go through it |
| refund approved / settled | `routers/orders.py::resolve_refund` for `approved` / `refunded`; `rejected` notifies nobody (D2) |
| password reset | **no hook** — no reset flow exists (F2.3 will add an email-only entry point to this service) |
| preorder | **no hook** — preorder is not orderable (`availability_issue`); B4.13 adds its type |

Recipients: the order/refund owner. SMS = profile phone, else the order's
shipping phone, normalised to ASCII digits; email = the account email. Messages
are Persian with Persian digits (order numbers, amounts in the storefront's
`۱,۲۵۰,۰۰۰` format); tracking and bank codes stay Latin so they can be copied.

### Admin controls

`notification_settings` (single row, `id = true`, both switches default **off**) +
`GET/PATCH /admin/settings/notifications` + `/admin/settings` page: in-app card
(locked-on switch, «همیشه فعال»), SMS (کاوه‌نگار) and email (SMTP) cards with a
switch, a «سرویس تنظیم شده/نشده» pill, a plain-language line on what will
actually happen, and the env-var names when unconfigured. Changes are audited
(`update_notification_settings` / entity `settings`, labelled in `/admin/audit`).
The tab is visible to admin/super_admin only; other roles get the shell's
permission notice on direct URL entry.

### SMS provider state

`KavenegarSmsProvider` implemented (`POST https://api.kavenegar.com/v1/{key}/sms/send.json`,
form `receptor`/`message`/`sender`, success = `return.status == 200`). **Not
configured, never called against the real API.** Tested only with
`httpx.MockTransport` (request shape, rejection, network failure, garbage body,
unconfigured → no call, key never in the error).

### Email provider state

`SmtpEmailProvider` implemented (stdlib `smtplib` in a worker thread; STARTTLS on
587 by default, implicit TLS via `SMTP_SSL=true`, optional login). **Not
configured, never connected to a real server.** Tested only with a stub `SMTP`
class (headers/body, STARTTLS + login, SSL mode, refused recipient → error
without the password, unconfigured).

### Frontend

- `NotificationBell` in `SiteHeader` for signed-in users: count badge (Persian
  digits, `۹۹+`), count in the `aria-label`, popover with the latest 6, «خواندن
  همه», skeleton / error + retry / empty states, rows that link to the order and
  mark themselves read, «مشاهده همه اعلان‌ها».
- `/account/notifications` tab: همه / خوانده‌نشده filter (with count), «خوانده
  شد» per item, «علامت‌گذاری همه…», `Pager` (10 per page), out-of-range page
  clamp, skeleton / error + retry / empty states, `head()`.
- `/admin/settings` as above.
- `src/lib/notifications.ts`: query keys scoped by user id (no cross-account
  cache bleed), 60 s unread polling, invalidation after every mark-read.
- **Shared-primitive fix (R7):** `ui/switch.tsx`'s checked thumb slid out of its
  track under `dir="rtl"` (measured: thumb x 163–179 vs track 129–165). Fixed in
  place with `rtl:data-[state=checked]:-translate-x-4`; the coupons page toggle
  had the same defect and is fixed too (measured inside the track afterwards).

## Files changed

Backend: `app/services/notifications.py` (new), `app/services/notification_providers.py` (new),
`app/routers/notifications.py` (new), `app/db.py`, `app/config.py`, `app/main.py`,
`app/auth.py`, `app/services/roles.py`, `app/services/audit.py`,
`app/services/checkout.py`, `app/services/payments.py`,
`app/services/order_lifecycle.py`, `app/routers/orders.py`,
`tests/test_notifications.py` (new), `tests/api_smoke.py`, `.env.example`, `README.md`.

Frontend: `src/components/NotificationBell.tsx` (new), `src/lib/notifications.ts` (new),
`src/routes/_authenticated/account.notifications.tsx` (new),
`src/routes/_authenticated/admin.settings.tsx` (new), `src/lib/api.ts`,
`src/components/SiteHeader.tsx`, `src/components/ui/switch.tsx`,
`src/routes/_authenticated/{account,admin,admin.audit}.tsx`, `src/routeTree.gen.ts`
(generated), `FEATURES.md`, `DESIGN_SYSTEM.md`.

Infra: `infra/docker-compose.yml` (provider env passthrough, empty defaults),
`infra/.env.example`, `infra/README.md`.

Docs: `AGENTS.md` (R7 summary line), `plan/RULES.md` (canonical table + guard
list), `plan/MASTER-BACKLOG.md`, `plan/backend-tasks.md`, `plan/frontend-tasks.md`,
`plan/feature-roadmap.md`, `plan/session-log.md`, this audit.

## How to verify

```bash
# backend (the DB tests need DATABASE_URL exported — see B6.13)
cd backend
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres JWT_SECRET=test-secret \
  ./.venv/bin/python -m pytest -q tests/test_notifications.py      # 45 passed
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres JWT_SECRET=test-secret \
  ./.venv/bin/python -m pytest -q                                  # 137 passed
./.venv/bin/python -m ruff check app tests
./.venv/bin/python tests/api_smoke.py                              # 224 checks, 0 failed

# frontend (bun lives in the frontend container)
cd infra && docker compose exec frontend sh -c 'bunx tsc --noEmit && bun run lint && bun run build'

# clean environment (Rule 14)
cd infra && docker compose down -v && docker compose up -d --build
docker compose logs db-init          # exit 0, four seed stages
curl -fsS http://localhost:8000/health
```

Manual: sign in as `customer@sande.local`, place and pay an order → the bell
shows ۲; open it → «پرداخت سفارش تأیید شد» above «سفارش شما ثبت شد»; as
`admin@sande.local` open «تنظیمات» → both providers «سرویس تنظیم نشده»; flip SMS
on → the card says nothing will be sent until the service is configured.

## Verification results

| Check | Result |
|---|---|
| `tests/test_notifications.py` | **45 passed** (15 pure: messages, Kavenegar ×5, SMTP ×4, config; 30 live-DB) |
| Mutation checks | dedup broken → 5 fail; switch ignored → 5 fail; `sent` rows re-dispatched → 1 fail; cancel hook removed → 3 fail (all restored) |
| full `pytest -q` with `DATABASE_URL` exported | **137 passed** (92 before + 45) — dev stack and again on the clean stack |
| plain `pytest -q` (the documented command) | 77 passed, 60 skipped — pre-existing harness defect, now B6.13 |
| `ruff check app tests` | clean |
| `tests/api_smoke.py` | **224 checks, 0 failed** (dev stack and clean stack); new checks: envelope, one row per event across a paid-twice/cancelled/refunded order and a staff-cancelled order, newest-first, mark-read, foreign id 404, read-all → 0, anonymous 401, admin read + flip + restore, customer/support 403, empty PATCH 400 |
| frontend `tsc --noEmit` / `bun run lint` / `bun run build` | clean / 0 errors (15 pre-existing warnings) / OK |
| Headless Chromium B2.1 suite (58 checks) | **58/58** on three consecutive dev-stack runs after the last harness fix (an earlier run failed one error-state check on a fixed 10 s wait: React Query retries a failing list 3× with backoff, ~7 s, so the wait became 20 s — app unchanged); covers guest (no bell), empty inbox, badge ۲ → mark-all → ۰, newest-first, Persian order number, sr-only unread, shipped → ۱ → click opens `/account/order/<id>` and marks read, account page + filter + refresh + direct URL, 13-item paging (10 + 3), per-item read ۱۰ → ۹, list 500 → error + retry (page and popover), mobile 390 px (bell/popover fit, no horizontal scroll), admin settings render/toggle/toast/persist/refresh/restore, audit label, settings 500/403 states, support / order_manager / customer direct URL → permission notice, API PATCH 403 ×3, no page errors, no 5xx |
| Clean environment — `docker compose down -v && up -d --build` | `db-init` exit 0 through all four stages (auth, products, demo, coupons); postgres/minio/backend healthy; `/health` OK; both tables with their UNIQUE/CHECK constraints, partial indexes and cascades on the fresh DB; settings row present with both switches off; 0 notifications after seeding; provider env vars present and empty in the container |
| Clean stack: pytest / smoke | 137 passed / 224 checks, 0 failed |
| Clean stack: B2.1 browser suite | first run 57/58 (the settings-500 state check waited 8 s on a cold dev server → 20 s), rerun **58/58** |
| Clean stack: role/route regression sweep (54 checks: every admin route × admin / order_manager / support with tab gating, storefront + account routes as customer and guest, bell presence, coupon Switch geometry + toggle) | **52/54**. Tab gating unchanged for all three staff roles (+«تنظیمات» for admin only), every route renders, Switch thumb inside its track. The 2 failures are **pre-existing and unrelated**, each isolated: the coupon toggle is rejected by the API (`PATCH /coupons/{id}` → 422, `text/plain` body — F5.14, confirmed by curl), and the seeded customer is signed out mid-run because `AuthProvider.refresh()` drops the token on any `/auth/me` failure (F5.15, reproduced identically with the bell removed). Earlier sweep runs failed more because the harness used fixed 2 s sleeps against 5–13 s dev-mode page loads (a harness bug, not the app) |

**Verification level: fully verified** — for the internal notification
system, the admin switches and the provider layer *up to the provider boundary*.
**Real SMS/email delivery is not verified at any level**: no credentials exist,
and the adapters were exercised only against stub transports (B2.1a).

## Discovered work (recorded, not fixed)

| ID | Discovered as | Priority | What |
|---|---|---|---|
| B2.1a | NEW-B21-1 | P3 | Activate the real providers once credentials exist; live-verify one SMS and one email |
| B5.1d | NEW-B21-2 | P2 | `record_audit` swallows an insert failure with `session.rollback()`, silently discarding the audited mutation while the router still answers 200 |
| B6.13 | NEW-B21-3 | P2 | The documented `pytest -q` skips every live-DB test (dummy `DATABASE_URL` from `test_addresses.py` wins the cached settings) |
| F5.13 | NEW-B21-4 | P3 | Guest direct-load of a protected `ssr:false` route logs a React hydration mismatch after the client redirect (identical with the bell removed — pre-existing) |
| F5.14 | NEW-B21-5 | **P1** | Admin coupon create / edit / toggle all fail with 422: `api.adminCreateCoupon` / `adminUpdateCoupon` send `body: JSON.stringify(…)` without the JSON content type, so FastAPI sees `text/plain` (curl: same body 200 as JSON, 422 as text/plain). Pre-existing; **set as the next pointer** — a shipped feature is broken today |
| F5.15 | NEW-B21-6 | P2 | `AuthProvider.refresh()` clears the token on *any* `/auth/me` failure (network error, restart, navigation-interrupted request), not only 401 — users get signed out; reproduced identically without the bell |

Hand-offs written into existing tasks: B2.5 must add the sweeper for
`pending`/`failed` deliveries; F2.3 must add an email-only entry point to the
notification service (and decide how to verify without SMTP); B4.13 adds the
preorder type.

## What is NOT done / open

- **No real SMS or email has ever been sent.** Both providers are unconfigured
  and default off; activation is B2.1a.
- No retry worker/sweeper: a delivery left `pending` by a crash, or `failed` by
  the provider, stays so until B2.5 (dispatch is retry-safe already).
- No hook for password reset (F2.3) or preorder (B4.13) — neither flow exists.
- Not in D2 scope, so not built: operations-team alerts (spec `[BE-07]`),
  "delivered" and "refund rejected" notifications, notification deletion/archiving
  and retention (the user asked for none), push/real-time updates (the bell polls
  every 60 s).
- No admin view of the delivery outbox (`notification_deliveries` is inspectable
  in SQL only).
- The staff member's own bell shows only notifications about *their own* orders —
  staff do not get operational notifications.
- `design/SANDE_FULL_DEV_SPEC.md` Part C #8 still says "Pending" — the user's
  document, not edited.
- `vogue-vintage-vibes/README.md` untouched: it lists no routes or scripts that
  changed.
- The Master Backlog JSON still uses `NEW-B68-1` / `NEW-B69-1` as ids although
  `backend-tasks.md` already names them B6.8a / B6.9a — a pre-existing
  inconsistency, left for a backlog-reconciliation pass (not this task).
