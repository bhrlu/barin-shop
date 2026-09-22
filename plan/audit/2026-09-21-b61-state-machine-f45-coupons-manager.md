# Audit — 2026-09-21 — B6.1 order state machine + F4.5 coupons manager

## Task

Two tasks picked from the lists, in dependency order:

- **B6.1** (backend, new checkbox from spec **[BE-05]**): order lifecycle state
  machine — validate transitions on every status change, restore stock on
  cancellation, all inside the mutation's transaction.
- **F4.5** (frontend, spec **[FE-07]**): coupons manager — ticket-style cards,
  usage progress, active toggle, create/edit dialog — on top of the existing
  `/coupons` CRUD.

## Spec check (Rule 0)

- **[BE-05] followed:** transition validation ('cancelled' orders cannot move to
  'shipped'), stock restore on cancellation, audit-log insertion (already
  existed, kept), atomic transaction via the caller's session. Spec's
  `updateOrderStatus({...})` RPC signature is a Supabase-ism — the repo's
  equivalent is `PATCH /orders/{id}` + `POST /orders/{id}/cancel`, both now
  state-machine-guarded. `reserve/commit stock on payment success` is already
  B1.5 (checkout decrements transactionally); B4.9 (TTL reservation) remains a
  separate open task.
- **[FE-07] followed:** ticket-style cards, usage progress bar, active toggle,
  Jalali-friendly dates (repo `formatFaDate`). Spec's dedicated Jalali date
  *picker* adapted to a native date input (no Persian calendar JS in the repo;
  noted below).

## What was done

### B6.1 — `app/services/order_lifecycle.py` (new)

- `ALLOWED_STATUS_TRANSITIONS`: pending → processing → shipped → delivered;
  pending/processing → cancelled; delivered/cancelled terminal. Same-status
  writes stay legal (idempotent).
- `assert_transition` + `IllegalTransition(old, new)` — `PATCH /orders/{id}`
  now captures the old status first and returns **409** with a Persian message
  on illegal moves (422 still used for unknown status strings).
- `cancel_order_tx`: flips status **and** restores stock in the caller's
  transaction — used by `POST /orders/{id}/cancel` (existing behavior + restore)
  **and** by `PATCH` with `status=cancelled` (the admin dropdown offers «لغو
  شده», so both paths must behave identically).
- `restore_stock`: mirrors checkout's decrement order — variant rows first
  (guarded by an `information_schema` check for the `variant_id` column, which
  older stacks may lack), then the product aggregate. `products.id` is **TEXT**
  in this schema, so raw equality (like checkout), no UUID casts.
- Spec's «reserve stock on payment success» kept as-is: `payment-complete` moves
  paid orders to `processing`; the state machine does not fight it (that's a
  lifecycle-legal move owned by the payment flow).

### F4.5 — coupons manager

- `api.ts`: `AdminCoupon` type + `adminCoupons` / `adminCreateCoupon` /
  `adminUpdateCoupon` / `adminDeleteCoupon` / `adminGenerateCouponCode`
  (POST — the endpoint was GET in the first draft; caught live).
- **Backend gap found while wiring:** `/coupons/{id}` had no DELETE. Added
  `DELETE /coupons/{id}` (204, audited as `delete_coupon`, redemptions untouched
  — order history keeps its plain-integer discount).
- `admin.coupons.tsx`: filter chips (همه/فعال/غیرفعال/منقضی), ticket cards with
  notches, dashed terracotta border when active, copy-to-clipboard code,
  `Switch` active toggle (PATCH), usage progress bar (red at 100%), create/edit
  dialog (percent XOR amount enforced client-side, mirrors backend), code
  generator pre-filling + clipboard, delete with toast, skeleton/empty states.

## Files changed

- `backend/app/services/order_lifecycle.py` (new)
- `backend/app/routers/orders.py` (transition guard, cancel paths)
- `backend/app/routers/coupons.py` (DELETE endpoint)
- `backend/app/services/audit.py` (`delete_coupon` action)
- `backend/tests/api_smoke.py` (B6.1 flow, second order for isolation)
- `vogue-vintage-vibes/src/lib/api.ts`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.coupons.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx` (coupons tab)
- docs: audit (this file), task lists, session log, READMEs

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q && ./.venv/bin/python -m ruff check app tests
cd backend && ./.venv/bin/python tests/api_smoke.py     # 151 checks, 0 failed
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build
```

Smoke asserts the machine end-to-end on a second (still-pending) order:
pending→shipped and pending→delivered **409** · pending→processing **200** ·
processing→pending **409** · admin PATCH cancel **200** · stock **+1** after
cancellation · cancelled→processing **409** (cannot revive). Coupon CRUD was
verified live: list 200 · create 200/201 · patch 200 · delete 204 · generate
201 · unauthenticated 401.

Note: repeated smoke runs drain seed stock — the checkout sections skip (and
check counts vary, 123–153) when the first product is out of stock. Top up with
`docker exec sandeh-postgres-1 psql -U sande -d postgres -c "UPDATE products SET
stock=50 WHERE stock<10"` before a run that must exercise checkout.

## What is NOT done / open

- **B4.9 stock reservation with TTL** stays open (spec's reserve-on-payment part
  is B1.5-covered; the pre-order hold is not).
- The state machine is enforced at the API; no DB trigger. A rogue SQL writer
  could still move statuses — acceptable for this stack, noted for B5.1b work.
- Jalali date **picker** on the coupon form is a native date input; a Persian
  calendar component would need a new dependency (user decision).
- Bulk coupon generation (`/generate?count=N`) not built — the spec doesn't ask;
  the single-code generator covers the UI's need.
