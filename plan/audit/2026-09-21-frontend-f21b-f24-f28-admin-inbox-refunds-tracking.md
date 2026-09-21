# Audit — 2026-09-21 — Admin inbox, refunds centre and shipment tracking (F2.1b + F2.4 + F2.8)

## Task

Three "quick wins" chosen by the user from `plan/frontend-tasks.md`, plus the two
small backend pieces they needed (logged first as new checkboxes per Rule 2):

- **F2.1b** — Admin contact inbox (read / mark answered / delete stored messages)
- **F2.4** — Admin refund-requests page (list + approve / reject / settle)
- **F2.8** — Shipment tracking number (admin input, shown to the customer)
- **B3.12** (new) — `orders.tracking_code` column + `PATCH /orders/{id}` support
- **B3.13** (new) — `PATCH /admin/contact-messages/{id}` mark answered

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before starting.

- **Followed:** [FE-06] shapes the refunds screen (tabs «در انتظار بررسی /
  تسویه‌شده / همه», claim card with the reason in a terracotta-edge quote box,
  rose mono amount, action dialog with «یادداشت مدیر»); B0.2 status semantics
  drive the badge colours; B0.3 `font-mono` for the tracking/contact codes; B4.3
  skeleton + empty states; B1.4 Persian copy + `toFa`/`formatToman`/`formatFaDate`;
  B1.1 no hardcoded palette classes; B5 `head()` with a unique Persian title and
  `robots: noindex` on both new routes.
- **Deliberately ignored / deferred:**
  - [FE-06]'s required «کد رهگیری بانکی (پایا/ساتنا)» input on settlement — the
    `refund_requests` table has no `bank_tracking_code` column yet (backend task
    **B5.3**); the dialog records the admin note only. Adding the input before the
    column exists would silently drop data.
  - [FE-05]'s order **drawer** for the tracking input — the task list keeps the
    drawer as F4.4; F2.8 puts the field in the order row so the capability lands
    now without pre-empting the drawer design.
  - The spec's stack (Supabase / `createServerFn`) is stale repo-wide (Rule 0.2);
    everything talks to FastAPI through `src/lib/api.ts` as the repo does.
  - No new shadcn primitives were needed beyond `dialog`/`textarea`/`button`
    (already present), so §3.2 inventory is unchanged.

## What was done

**Backend (additive only — Rule 4 respected):**

- `app/db.py`: new idempotent `TRACKING_DDL` adds `orders.tracking_code TEXT`
  (NULL until an admin sets it); wired into `startup_ddl`.
- `app/models.py`: `Order.tracking_code` mapped column.
- `app/routers/orders.py`: `_ORDER_SELECT` now returns `o.tracking_code`;
  `OrderPatch` accepts `tracking_code` (max 60 chars, empty string clears it).
  The payment-session `tracking_code` (the simulated gateway's `SND-…` session
  code) is a different pre-existing value and is untouched.
- `app/routers/contact.py` + `app/schemas.py`: new
  `PATCH /admin/contact-messages/{id}` with `ContactMessageStatusIn`
  (`Literal["new", "answered"]` → unknown statuses 422), returning the updated
  message.
- `tests/api_smoke.py`: new checks — mark answered, `?status=answered` filter,
  422 on bogus status; admin orders carry `tracking_code`, admin can set it,
  customer sees it, empty string clears it, customer gets 403.

**Frontend:**

- `src/lib/api.ts`: `Order.tracking_code`, `ContactMessageStatus` type, client
  methods `adminContactMessages` / `markContactMessage` / `deleteContactMessage`;
  `patchOrder` accepts `tracking_code`.
- `src/lib/orders.ts`: `REFUND_STATUS` labels (`requested` DDL default kept, so
  existing rows never break; unknown statuses fall back to the raw string).
- **`/admin/messages`** (`admin.messages.tsx`, F2.1b): filter chips (همه /
  پاسخ‌داده‌نشده / پاسخ‌داده‌شده), Jalali dates, copy-to-clipboard on the sender's
  contact, mark answered ↔ reopen, delete — all with sonner toasts and
  skeletons/empty states.
- **`/admin/refunds`** (`admin.refunds.tsx`, F2.4): the three [FE-06] tabs, claim
  cards, and `RefundActionDialog` (approve / reject / settle) hitting
  `PATCH /refunds/{id}`; settling also flips the order's payment status
  server-side (pre-existing behaviour), and admin stats/payments queries are
  invalidated.
- `admin.orders.tsx` (F2.8): per-order tracking input (save on submit, explicit
  حذف clears, dirty-check disables the button) plus a «کپی آدرس» action.
- `account.order.$orderId.tsx` (F2.8): customers see «کد رهگیری مرسوله» in the
  stepper box once an admin has set it (hidden for cancelled orders).
- `admin.tsx`: two new tabs — بازپرداخت‌ها and پیام‌ها.
- `routeTree.gen.ts` regenerated for the two new routes.

## Files changed

Backend:
- `backend/app/db.py`
- `backend/app/models.py`
- `backend/app/routers/orders.py`
- `backend/app/routers/contact.py`
- `backend/app/schemas.py`
- `backend/tests/api_smoke.py`

Frontend:
- `vogue-vintage-vibes/src/lib/api.ts`
- `vogue-vintage-vibes/src/lib/orders.ts`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.messages.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.refunds.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.orders.tsx`
- `vogue-vintage-vibes/src/routes/_authenticated/account.order.$orderId.tsx`
- `vogue-vintage-vibes/src/routeTree.gen.ts` (generated)

## How to verify

Backend (unit + lint):

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests             # clean
```

Live end-to-end (needs the Docker stack up — verified against it, the API
hot-reloaded the new code):

```bash
cd backend && ./.venv/bin/python tests/api_smoke.py
# → "117 routes/checks, 0 failed", including:
#   PATCH /admin/contact-messages/{id} marks answered
#   answered message appears under ?status=answered
#   PATCH /orders/{id} saves tracking_code
#   customer order shows tracking_code
#   empty tracking_code clears the field
#   customer cannot set tracking_code (403)
```

Frontend typecheck (build blocked by the environment — see "open"):

```bash
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit   # clean
```

Manual: sign in as an admin → `/admin` → «پیام‌ها» and «بازپرداخت‌ها» tabs exist;
submit a contact form message from `/contact` and mark it answered; open an
order in «سفارش‌ها», save a tracking code, then view the same order as the
customer (`/account/orders/{id}`) — the code appears under the stepper.

## What is NOT done / open

- **Refund settlement bank-tracking input** waits on **B5.3** (needs
  `refund_requests.bank_tracking_code` + the `requested`/`pending` vocabulary
  decision; `REFUND_STATUS` already tolerates both worlds).
- **F4.4 order drawer / invoice printing** not attempted — the tracking input
  lives in the order row for now.
- **Frontend `vite build` fails in this shell** with
  `Cannot find native binding … @rolldown/binding-darwin-arm64`: the local
  `node_modules` was installed with npm against a Bun lockfile, and the default
  node (20.9.0) is older than rolldown-vite requires. Pre-existing environment
  issue, unrelated to this task; `tsc --noEmit` passes and the smoke test
  verifies the API side. Rebuilding the container image (which uses Bun) is the
  reliable path.
- **No notification** is sent when a tracking code is set or a refund resolved —
  that is B2.1 (SMS/email), untouched.
- Docs updated in the same task: `frontend-tasks.md` (F2.1b/F2.4/F2.8 ticked +
  audit link), `backend-tasks.md` (B3.12/B3.13 added + ticked), `session-log.md`
  (Session 12), `backend/README.md` (PATCH /orders tracking + contact PATCH row),
  `vogue-vintage-vibes/FEATURES.md` (gaps ۶.۳/۶.۱۰/۶.۱۴ resolved),
  `vogue-vintage-vibes/DESIGN_SYSTEM.md` (§3.3 today column + §8 note 9),
  `plan/README.md` (audit index). Not touched: `plan/feature-roadmap.md` (the
  F2.4/F2.8 entries there point at the same work as the task list; roadmap says
  "see task list" for these), `infra/README.md` (no infra change).
