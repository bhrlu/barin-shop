# Audit — non-admin slice: contact form, address defaults, payment authority (B3.4 · B3.7 · F2.1 · F2.7)

**Date:** 2026-09-21
**Task:** continue the remaining **non-admin** backend + frontend work. Admin/back-office
work was explicitly out of scope (the `plan/ADMIN-*.md` task split was left untouched).

Chosen slice (all customer-facing, no admin screens):

| Item | What it was |
|---|---|
| **B3.7** | payment authority was not persisted → a repeat Zarinpal callback returned **400** instead of `already_paid` |
| **B3.4** | stale Supabase wording in `app/db.py`, `models.py`, `auth.py`, `storage.py`, `seed_products.py` |
| **F2.1** | the contact form was a display-only toast; nothing was stored, and the backend had no `/contact` route |
| **F2.7** | `addresses.is_default` existed in the DB with **no UI**, and checkout ignored saved addresses |
| **+ new** | `province` was collected on saved addresses and asked for by the spec's shipping box, but the checkout payload dropped it |

## Spec check (Rule 0)

Read [`design/SANDE_FULL_DEV_SPEC.md`](../../design/SANDE_FULL_DEV_SPEC.md) before
starting, per Rule 0.1/0.2:

| Spec section | Taken? | Note |
|---|---|---|
| B3 `[FE-05]` shipping box — «name, phone, **province**, city, full address, postal code» | **followed** | This is the gap this task found: the checkout form and `CheckoutAddress` had no province. Now optional on the API (`province: str \| None`) so older payloads keep working, and sent by the form. |
| B3 `[FE-08]` customer tabs — «تاریخچه سفارشات · **آدرس‌های ثبت‌شده** · علاقه‌مندی‌ها» | **partly followed** | The account addresses tab is the customer-facing half and now shows/moves the default. The CRM drawer itself is admin work → not in this task. |
| B0/B1 UI/UX invariants (semantic tokens, Persian copy, RTL logical props, `rounded-none` on storefront inputs) | **followed** | New UI uses `bg-sand`, `border-terracotta`, `text-terracotta`, `rounded-none`; no raw `bg-emerald-*`-style classes. |
| Contact form | **not in the spec** | No section covers it; designed from the repo's own conventions (Query mutation + Sonner toast, same sand panel). |
| Stack header (Supabase / Lovable Cloud / `createServerFn`) | **ignored per Rule 0.2** | The repo is FastAPI-only; the new endpoints are plain FastAPI routes. |
| `plan/ADMIN-BACKEND_TASKS.md` · `plan/ADMIN-FRONTEND_TASKS.md` | **out of scope** | Back-office split; untouched by instruction. |
| Spec file itself | **not edited** (Rule 0.4) | Its staleness is already carried by `DESIGN_SYSTEM.md` §5. |

## What was done

### B3.7 — the gateway authority has its own column
- `payments.authority` + an index, added **idempotently on startup**
  (`app/db.py`, same pattern as the catalog columns). `reference` still starts as
  the authority so a pending row reads exactly as before, then becomes the
  `SND-…` code on success.
- `verify_and_finalize()` looks the session up by authority (with a
  `reference = :authority` fallback for rows written before the column existed)
  and returns **`already_paid`** when the row is already settled instead of
  raising "session not found".
- The callback takes the order id straight from the verify result, so a repeated
  gateway hit still redirects to the right order page. Status strings
  (`pending/succeeded/failed`, `unpaid/paid/refunded`) are untouched.

### B3.4 — no Supabase wording left in `app/`
Docstrings/comments in `db.py`, `models.py`, `auth.py`, `storage.py`,
`seed_products.py` now describe the FastAPI + own-JWT + MinIO reality.
`grep -ri supabase backend/app backend/tests` → nothing.

### F2.1 — the contact form persists
- New `public.contact_messages` (`app/db.py`) and `app/routers/contact.py`:
  - `POST /contact` — **public** (a guest can ask about a size without an
    account), `user_id` stays NULL, the sender's own `contact` field is the way
    back. Validation: name ≥ 2, contact ≥ 5, message ≥ 5 chars.
  - `GET /admin/contact-messages?status=` (admin) and
    `DELETE /admin/contact-messages/{id}` (admin).
- `contact.tsx` is now a real form (controlled state, `useMutation`, min-length
  attributes mirroring the API, Persian success/error toasts, inline confirmation
  copy instead of the old «نمایشی» note). **There is no admin screen for the
  inbox yet** → logged as **F2.1b**.

### F2.7 — saved addresses have a single default and checkout uses it
- `app/routers/addresses.py`: at most one `is_default` per customer — the first
  address becomes the default automatically, an explicit `is_default` moves the
  flag, and deleting the default promotes the most recent survivor. New
  **`PATCH /addresses/{id}`** edits fields and/or moves the default (404 for
  someone else's address).
- Account tab: «پیش‌فرض» badge, a «انتخاب به‌عنوان پیشفرض» action, a
  «این آدرس پیشفرض باشد» checkbox on create.
- `checkout.tsx`: a saved-address picker above the form (default pre-selected,
  «آدرس جدید» clears it), fields pre-filled from the picked address via a remount
  key, and `province` added to the form + payload (see the spec check above).

### Frontend client
`src/lib/api.ts`: `ContactMessage` type, `api.contact()`, `api.updateAddress()`,
`CheckoutAddress.province`.

## Files changed

**Backend**
- `backend/app/db.py` (contact_messages table DDL, authority column + index)
- `backend/app/routers/contact.py` **(new)**, `backend/app/routers/addresses.py` (rewritten)
- `backend/app/routers/payments.py`, `backend/app/services/payments.py` (B3.7)
- `backend/app/main.py` (router registration)
- `backend/app/schemas.py` (`ContactMessageIn/Out`, `AddressUpdateIn`,
  `CheckoutAddress.province`)
- `backend/app/services/checkout.py` (province in `shipping_address`)
- `backend/app/models.py`, `routers/auth.py`, `routers/storage.py`, `seed_products.py` (B3.4)
- `backend/tests/api_smoke.py`
- `backend/README.md`

**Frontend**
- `vogue-vintage-vibes/src/lib/api.ts`
- `.../src/routes/contact.tsx`, `.../src/routes/checkout.tsx`,
  `.../src/routes/_authenticated/account.addresses.tsx`
- `vogue-vintage-vibes/FEATURES.md`, `vogue-vintage-vibes/DESIGN_SYSTEM.md`

**Plan**
- `plan/backend-tasks.md` (B3.4/B3.7 ticked, B3.9 added)
- `plan/frontend-tasks.md` (F2.1/F2.7 ticked, F2.1b/F2.7b added)
- `plan/session-log.md` (Session 18), `plan/feature-roadmap.md`, `plan/README.md`

## How to verify

```bash
cd backend
./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests
./.venv/bin/python tests/api_smoke.py    # 97 routes/checks, 0 failed (needs the stack up)

cd ../vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/eslint src/routes/contact.tsx src/routes/checkout.tsx \
  src/routes/_authenticated/account.addresses.tsx src/lib/api.ts
```

What the suite actually asserts for this task (live stack):
- `POST /contact` → 201 and `GET /admin/contact-messages` shows the row
  (deleted again afterwards); too-short bodies → 422.
- default-address invariant: two addresses → exactly one default; `PATCH` with
  `is_default` moves it and sets fields; deleting the default promotes the
  survivor; unknown id → 404.
- `repeat gateway callback is idempotent (not 400)` and
  `POST /payments/verify on a settled session → already_paid`.
- `checkout keeps province + postal code in shipping_address`.

Manual spot checks against the running stack (localhost:8000) were also used for
the payment callback and the address invariant before the smoke script grew those
assertions.

## What is NOT done / open

- **No admin UI for contact messages** (`F2.1b`) — the inbox API exists, nothing
  reads it yet. Same situation as refunds (F2.4): backend ready, screen missing.
- **No spam guard on the public `POST /contact`** — no rate limit, honeypot or
  captcha → logged as **B3.9**. It is an unauthenticated write endpoint.
- **The address book cannot be edited field-by-field in the UI** — `PATCH
  /addresses/{id}` supports it, but the screen only uses it to move the default
  → logged as **F2.7b**.
- **No browser pass** on contact/checkout/addresses: `vite` still cannot start in
  this environment (pre-existing Node 20/22 + rolldown binding issue noted in the
  previous audits), so the UI changes are verified by `tsc` + eslint + the API
  shapes they read, not by clicking.
- **`province` is free text** — the spec implies a province list for shipping;
  a fixed list + validation is not implemented (no task logged; only worth it
  together with real carrier rates).
- **Preorder is still not orderable** (B4.13) and the other non-admin items on
  the list remain: **F2.3** forgot-password (needs a reset-token endpoint +
  email → blocked on B2.1), **F2.5** pagination, **F2.6** dashboard charts,
  **F2.8** tracking number, and Milestone **B2** (notifications, exports,
  invoices, jobs).
- `infra/initdb/02-public-schema.sql` was **not** touched: `contact_messages` and
  `payments.authority` are additive DDL applied by `app/db.py` on startup, which
  is the existing convention for `coupons`, `product_variants`, `product_reviews`,
  `search_history` and `recently_viewed`. No compose/env/script change → `infra/README.md`
  left alone.
- `plan/ADMIN-BACKEND_TASKS.md` / `plan/ADMIN-FRONTEND_TASKS.md` were **not**
  modified (admin scope, out of this task) — they are now indexed in
  `plan/README.md` so they stop being invisible.
