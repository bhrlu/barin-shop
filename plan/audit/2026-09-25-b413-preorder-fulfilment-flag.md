# 2026-09-25 — B4.13 Preorder fulfilment flag

## Task

`plan/MASTER-BACKLOG.md` §B4.13 (Batch F, P3, backend): allow preorder
checkout, persist a preorder marker, avoid physical stock decrement, expose
preorder state to admin, use `available_at` as fulfilment-readiness
information, integrate applicable notifications. Dependencies: B2.1 (DONE),
decision D4 (preorder policy — resolved), decision D2 (notification path —
shipped in B2.1).

## Spec check (Rule 0)

Sections consulted via the CONTEXT-MAP spec index: [BE-05] atomic inventory
consistency (cancellation mirrors checkout), [BE-01] inventory ledger,
B1.4 Persian digits (notification copy), B4.1 `formatToman` shape (`toman()`).
The spec has **no preorder section** (grep for `preorder|available_at` → 0
hits) — decision D4 in the Master Backlog is the authority for the policy.
No conflicts found; no spec file was edited.

## What was done

1. **`order_items.is_preorder BOOLEAN NOT NULL DEFAULT false`** — idempotent
   column in `CATALOG_DDL` (`app/db.py`), so legacy rows read as non-preorder.
   No new order **status** string was created (the task's explicit constraint;
   `pending/processing/shipped/delivered/cancelled` untouched).
2. **`availability=preorder` is orderable** — `availability_issue()` returns
   `None` for `preorder` (was `not_available`); new `is_preorder()` helper in
   `app/services/availability.py` is the single flag source (R7). `coming_soon`
   stays blocked.
3. **Checkout skips stock for preorder lines** (`app/services/checkout.py`):
   the sufficiency check at validation **and** the decrement + `purchase`
   ledger row at step 7 are both skipped per preorder line. This fixed a real
   contradiction in the draft found during the session: the draft still
   rejected preorder lines with `insufficient_stock` while skipping the
   decrement — under D4 ("the physical unit does not exist yet") a preorder
   product typically has stock 0, so nothing could ever be bought, and the
   cart would have blocked what checkout accepted. The stock counter on a
   preorder product is an operational allocation, never the gate; nothing can
   oversell because nothing is decremented.
4. **`POST /stock/check` mirrors checkout** (`app/routers/stock.py`): same
   sufficiency skip for preorder lines, so the pre-check and the order can
   never disagree (the shared `availability`/`variants` helpers already
   guaranteed the rest).
5. **Cancellation restores nothing for preorder lines**
   (`app/services/order_lifecycle.py`): `restore_stock` filters `is_preorder`
   lines out of both the stock bump and the `return` ledger row — purchase
   and return net to zero and the ledger stays a true mirror.
6. **Order payloads expose the flag** (`app/routers/orders.py`):
   `_ORDER_SELECT` now returns `is_preorder` per item — this covers the
   customer endpoints and `GET /admin/orders` (which reuses the select), so
   admin can identify preorder items (D4). Frontend `OrderItem` type gained
   the additive `is_preorder: boolean` field.
7. **Notification (B2.1 hand-off)**: `order_created_preorder` type added to
   `TYPES` in `app/services/notifications.py` with the standard D2 channel
   set; checkout fires it (instead of `created`) when any line is preorder,
   with the same `order:<id>:<event>` dedup key; Persian message: «پیش‌خرید
   شماره … ثبت شد. پس از عرضهٔ محصول ارسال می‌شود.»

## Deliberate interpretation (recorded, per R15)

D4 says a preorder "does not decrement **physical** stock". Implemented as:
the preorder line still validates activity/availability/size/variant-active,
but never the stock counter, and never touches stock or the ledger. The
alternative (requiring stock ≥ qty while not decrementing) was in the draft
and rejected: it could not be oversold either, but it blocked the typical
stock-0 preorder and contradicted the D4 wording. `available_at` remains the
operational fulfilment signal (admin-visible on the product; no automatic
fulfilment worker, per D4).

## Tests

* `tests/test_availability_and_filters.py` — stale `test_preorder_is_blocked`
  flipped to `test_preorder_is_blocked`→`test_preorder_is_orderable` (D4);
  new `TestIsPreorder` (5 cases: preorder/in_stock/coming_soon/missing/null).
* `tests/test_preorder_fulfilment.py` — new DB-backed module (8 tests, skips
  without Postgres like `test_order_lifecycle_stock.py`, throwaway
  product/user with teardown): preorder orderable at stock 0; product stock
  unchanged; **no `purchase` ledger row**; `is_preorder` persisted on the
  item; mixed order splits behaviour per line (normal −2, preorder untouched,
  exactly one ledger row); `order_created_preorder` notification fired with
  the `order:<id>:created_preorder` key and idempotent on replay; cancelling a
  preorder restores nothing (no `return` row); mixed-order cancel restores
  only the normal line.

## Verification

* `ruff check app tests` — clean.
* `pytest -q` — **377 passed** (was 364; +13 new, 0 skipped DB modules).
* Live stack (compose up): smoke `tests/api_smoke.py` — **257 routes/checks,
  0 failed**; `is_preorder` column present in the running DB (startup DDL
  applied by the running app's boot).
* Live acceptance probe (real endpoints, throwaway rows hard-deleted after —
  0 probe products/orders/notifications remain): preorder product at stock 0 →
  `POST /stock/check` `ok:true` → `POST /checkout` 200 → order payload
  `is_preorder: true` on both customer and admin shapes → `POST
  /payments/start` + simulated-gateway callback → order `processing/paid` →
  `POST /orders/{id}/cancel` 200. Matches the task's verification chain:
  preorder → checkout → payment → marked preorder → stock unchanged → admin
  identifies item, plus cancellation.
* Frontend: `tsc --noEmit` 0 errors (additive type field only; no UI change).

## What is NOT done / open

* **Storefront still disables add-to-cart for preorder** (`product.$id.tsx`
  `purchasable` gate and `VariantPicker`) — the D4 storefront flip is a
  separate frontend task; backend alone does not make it purchasable in the
  browser. New checkbox **F3.2c** in `frontend-tasks.md`.
* No preorder badge/label on cart/checkout/order items in the UI (same task).
* Fulfilment at `available_at` is operational (admin works the order when the
  date arrives) — no automatic worker (D4 explicitly).
* B6.18a (restock trigger) unchanged; preorder fulfilment does not consume it.

## Backlog / docs synced

`MASTER-BACKLOG.md` (§B4.13 section, JSON index entry, `agent_start_task`/NEXT
→ AB-FE-06, counts 52 DONE / 6 TODO of 58, B2.1/B2.5 dependency notes),
`backend-tasks.md` (checkbox + note), `frontend-tasks.md` (F3.2c + F3.2b
wording), `feature-roadmap.md` (roadmap row), `session-log.md`.
