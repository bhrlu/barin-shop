# Audit — 2026-09-21 — B5.3 refund bank-tracking fields (backend + F2.4 dialog completion)

## Task

**B5.3** from `plan/backend-tasks.md`: add the `bank_tracking_code`,
`resolved_by` and `resolved_at` columns to `refund_requests` that the spec's
approval flow expects, and reconcile the status vocabulary — completing the
settlement UI the F2.4 refunds centre has been waiting for.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before starting (re-verified against
[BE-03] and [FE-06] which this task implements directly).

- **Followed:**
  - [BE-03] column set — `bank_tracking_code` (VARCHAR NULLABLE),
    `resolved_by` (UUID FK → users NULLABLE), `resolved_at` (TIMESTAMPTZ
    NULLABLE). The FK points at this repo's `public.users` (no `auth.users` —
    stale stack, Rule 0.2).
  - [BE-03]/[FE-06] status vocabulary `pending/approved/rejected/refunded` —
    reconciled exactly as the task line required: new rows insert `pending`
    explicitly; a startup UPDATE normalizes legacy `requested` rows; already
    settled rows are untouched (Rule 4: no existing status strings change).
  - [FE-06] action dialog — required «کد رهگیری بانکی (پایا/ساتنا)» input on
    settlement, admin-note textarea, claim-card display of the code on settled
    cards, Persian labels throughout.
- **Deliberately ignored / adapted:**
  - [BE-03]'s `admin_notes` (plural) — the table already has `admin_note`
    (singular) from the base DDL; renaming would break existing rows and the
    shipped API contract (Rule 4). The spec's intent (a nullable admin note) is
    met by the existing column.
  - [BE-03]'s RLS policies — this repo has no RLS; authz is the
    `AdminUser`/`CurrentUser` FastAPI dependencies (sole-backend architecture,
    Rule 0.2). Ownership is enforced where the spec's policy would be: a
    customer can only refund their own cancelled+paid order (`request_refund`).
  - Spec's Sheba/card-number copy button on claim cards — `refund_requests`
    stores no Sheba; the claimant's email is shown instead. Real Sheba capture
    would need a new column (not in any task; noted as an idea, not added).

## What was done

**Backend:**

- `app/db.py`: new idempotent `REFUND_DDL` — the three columns
  (`bank_tracking_code TEXT`, `resolved_by UUID REFERENCES users ON DELETE SET
  NULL`, `resolved_at TIMESTAMPTZ`) plus the vocabulary UPDATE
  (`requested` → `pending`). Wired into `startup_ddl` between `TRACKING_DDL`
  and `PAYMENT_DDL`.
- `app/models.py`: new `RefundRequest` ORM model mirroring the table (the
  routers keep raw SQL; the model documents the shape and keeps
  `models.py` complete).
- `app/routers/orders.py`:
  - `RefundResolveIn` gained `bank_tracking_code` (≤ 60 chars).
  - `resolve_refund` rejects `refunded` without a non-blank bank code (422,
    Persian message); accepts the code for any resolution and stores it via
    `COALESCE` (re-settlement updates, never wipes).
  - Every resolution stamps `resolved_by` (admin id) and `resolved_at` (now()).
  - `request_refund` inserts `status = 'pending'` explicitly.
- `app/routers/admin.py`: `GET /admin/refunds` joins `users` + `profiles` and
  returns `user_email` + `user_name` (`COALESCE(profiles.full_name, email)`)
  so the UI can show who claimed the refund.

**Frontend:**

- `src/lib/api.ts`: `RefundRequest` extended with `bank_tracking_code`,
  `resolved_by`, `resolved_at`, `user_email`, `user_name`;
  `resolveRefund` accepts and sends `bank_tracking_code`.
- `src/routes/_authenticated/admin.refunds.tsx`:
  - `RefundActionDialog`: required, `dir="ltr"` mono input for the Paya/Satna
    code (pre-filled on re-open), helper line explaining why it is mandatory;
    the settlement button is disabled while it is empty — mirroring the
    backend's 422.
  - Claim cards show the claimant (`user_name` · `user_email`); settled cards
    show the bank tracking code + settlement date.
- **Removed `vogue-vintage-vibes/package-lock.json`** — a stale npm artifact
  (the npm install that caused this morning's broken `node_modules`); `bun.lock`
  is the only lockfile. Cleanup related to this morning's `fix(env)` commit.

**Tests:**

- `tests/api_smoke.py`: full refund flow added — cancel a paid order, request
  the refund, assert `pending` on create, claimant contact in the admin list,
  **422 on settlement without the bank code**, successful settlement with the
  code, bank code + `resolved_by` + `resolved_at` recorded, and the order's
  `payment_status` flipping to `refunded`.

## Files changed

- `backend/app/db.py`
- `backend/app/models.py`
- `backend/app/routers/orders.py`
- `backend/app/routers/admin.py`
- `backend/tests/api_smoke.py`
- `vogue-vintage-vibes/src/lib/api.ts`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.refunds.tsx`
- `vogue-vintage-vibes/package-lock.json` (deleted)
- Docs: `plan/backend-tasks.md`, `plan/frontend-tasks.md`, `plan/README.md`,
  `plan/session-log.md`, `backend/README.md`, `vogue-vintage-vibes/FEATURES.md`,
  `vogue-vintage-vibes/DESIGN_SYSTEM.md`, this audit.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests             # clean
```

Live end-to-end (Docker stack up; the API hot-reloaded the new code and ran
`REFUND_DDL` at startup):

```bash
cd backend && ./.venv/bin/python tests/api_smoke.py
# → "130 routes/checks, 0 failed", including:
#   refund request starts as pending
#   admin refund list carries claimant contact (user_email=…)
#   settlement without bank tracking code is rejected (422)
#   settlement with bank code succeeds
#   settled refund records bank code + resolver (SATNA123456, admin UUID, ts)
#   settled refund flips order payment_status to refunded
```

Frontend:

```bash
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit   # clean
bun run build                                                # passes
```

Manual: admin → `/admin/refunds` → a pending claim shows the claimant; open
«رسیدگی به درخواست» → the bank-code field is required and the settlement button
stays disabled until it is filled; after settling with a code, the settled card
shows the code and settlement date, and the order's payment status reads
«بازگشت داده شده».

## What is NOT done / open

- **Sheba/card-number capture** — [FE-06] also pictures a Sheba on the claim
  card with a copy button; the schema has no column for it. Not added (no task
  covers it); the claimant's email is shown instead.
- **No SMS/email notification** on settlement — still B2.1.
- **Admin audit log** for the resolution — [BE-04]/B5.1 would record the refund
  resolution as an audited action; untouched (B5.1 is still open).
- The stale `package-lock.json` deletion rides with this task as related
  cleanup; `bun.lock` is unaffected.
- Docs updated in the same task (see list above). `infra/README.md` untouched —
  no infra surface changed (DDL is backend-owned and idempotent).
