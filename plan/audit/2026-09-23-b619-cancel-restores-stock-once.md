# Audit — B6.19 Concurrent cancellation restored stock twice (2026-09-23)

## Task

`B6.19` (**P1**, new). Found during AB-BE-01's recon (R10: "what if this runs
twice?"), while mapping every stock mutation for the inventory ledger.

`cancel_order_tx` trusted the status its caller had read **without a lock**. It then
ran `UPDATE orders SET status='cancelled' WHERE id=…` and restored the stock. Two
cancels racing could both pass the check and both restore:

- a customer's `POST /orders/{id}/cancel` and a staff `PATCH /orders/{id}
  {status: cancelled}`;
- or a double click.

It was fixed before AB-BE-01. Otherwise the new ledger would faithfully record two
"return" rows. Part of the "continue the whole backlog" run.

## Reproduction (before)

Probe against the live stack: checkout 2 units, then fire the customer cancel and the
staff PATCH concurrently, six times. **5 of 6 trials restored the stock twice**: +2
units beyond the original each time, e.g. `crop-5` 25 → 27. Both requests answered
200. The probe reset each product's stock afterwards.

## Spec check (Rule 0)

`[BE-05]`: an atomic transaction safeguards inventory consistency, and cancellation
restocks. This bug broke it under concurrency. No spec conflict.

## Recon / contract (Rules 6–10)

- **Owning module:** `services/order_lifecycle.py` (R7: transitions and stock restore
  live only there).
- **Callers:** `POST /orders/{id}/cancel` (customer) and `PATCH /orders/{id}` (staff,
  `status=cancelled`). Both read the order without `FOR UPDATE` (`_fetch_order`), and
  `grep` finds no `FOR UPDATE` on either path.
- **State machine:** cancellable from `pending` and `processing`;
  `cancelled` / `delivered` are terminal.
- **Contract:** unchanged on success. On a lost race:
  - `POST /cancel` returns the same idempotent `200 {ok: true, refund_eligible:
    false}` it already returns for an order read as cancelled;
  - `PATCH` returns 409, as for any refused cancel.

## What was done

- **`cancel_order_tx`** is a compare-and-set:
  `UPDATE … SET status='cancelled' WHERE id=:oid AND status = ANY(:cancellable)
  RETURNING id`.
  - A concurrent request blocks on the row lock, re-evaluates the `WHERE` after the
    first commits (READ COMMITTED), matches nothing and raises `CancelError`.
  - `already_cancelled=True` is set when the order is now cancelled. A move to a
    non-cancellable status in between (e.g. `shipped`) is refused with its status.
  - Stock is restored only by the request that flipped the row.
- **`CancelError`** gains `already_cancelled`.
- **`POST /orders/{id}/cancel`** maps `already_cancelled` to the idempotent 200.

## Files changed

- `backend/app/services/order_lifecycle.py`, `backend/app/routers/orders.py`
- `backend/tests/test_order_lifecycle_stock.py` (+4 tests)
- docs: `backend/README.md` (PATCH /orders row), this audit, `plan/MASTER-BACKLOG.md`,
  `plan/backend-tasks.md`, `plan/session-log.md`, `plan/README.md`

## How to verify

`pytest tests/test_order_lifecycle_stock.py`: 9 passed. The 4 new tests:

1. **Stale second cancel:** a second cancel with a stale `pending` raises
   `already_cancelled` and restores nothing.
2. **Two sessions racing** (one holds the row lock): outcomes `["already",
   "cancelled"]`, and the stock is restored once.
3. **A move between read and cancel** (`shipped`): refused, stock untouched.
4. **Through the real endpoints** (POST /cancel and PATCH concurrently, 3 rounds): the
   customer gets 200, staff 200/409, and the stock is back to exactly the
   pre-checkout value.

**Negative control:** with `HEAD`'s `order_lifecycle.py` + `orders.py`, all 4 new
tests fail and the 5 old ones pass.

**Live probe after the fix:** **0 of 6** double restores. The losing request answers
409 (PATCH) or the idempotent 200.

Full gates: `ruff` clean, `pytest -q` **246 passed**, smoke **241/0**.

No DDL, infra or seed change, so a clean environment is not required.

**Verification level:** integration tested (unit + live race probe).

## What is NOT done / open

- **Other status transitions** (e.g. two staff moving `processing → shipped` at once)
  still read without a lock. They have no stock side effect; notifications are
  deduped by `event_key` (B2.1), so a double write is harmless. No task added.
- `infra/README.md`, frontend docs: untouched (no UI change).
