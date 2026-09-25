# 2026-09-25 — F3.2c Storefront preorder purchase (D4 flip)

## Task

`plan/MASTER-BACKLOG.md` §F3.2c (JSON index; Batch F, P3, frontend; depends on
B4.13 DONE): `product.$id.tsx` and `VariantPicker` stop disabling preorder (the
backend accepts it since B4.13 — no stock gate, no decrement); preorder
badge/copy («پیش‌خرید» + `available_at`) on product page, cart and order items;
the cart's stock-check flow tolerates preorder lines. Decision D4 is the
authority for the policy; B4.13 is the backend contract this task surfaces.

## Spec check (Rule 0)

Sections consulted via the CONTEXT-MAP spec index: B4.1/B4.2 — reusable
formatting and status-badge blocks (the repo's canonical forms are
`formatToman`/`toFa` and the token classes already in use; no raw palette
introduced — the chip reuses the existing `bg-sage/25 text-sage-deep` pairing
from the product page). The spec has no preorder section (B4.13's audit grepped
it: 0 hits) — decision D4 stays the authority. Live-repo precedence applied:
the backend already accepts preorder (`/stock/check` and checkout skip the
sufficiency gate for preorder lines, B4.13), so the cart needed no code change
to *tolerate* preorder lines — only merchandising. No spec file edited.

## What was done

1. **`components/product/VariantPicker.tsx`** — the picker mirrors the backend
   rule per D4: on `availability=preorder` the physical count never gates, so
   sizes and colours stay selectable at stock 0; a **deactivated** variant row
   is still blocked (`available=false`) because activity is a merchandising
   decision, not stock. The selected-combo hint on preorder reads «پیش‌خرید —
   پس از عرضهٔ محصول ارسال می‌شود.» instead of the stock copies. `coming_soon`
   behaviour unchanged (still gated).
2. **`routes/product.$id.tsx`** — `purchasable` no longer excludes preorder:
   the gate is now `!comingSoon && comboOrderable`, where preorder requires an
   *active* combination (not a stock count). Quantity ceiling on preorder is
   the cart's 20-line cap, not stock. `handleAdd` splits the guard
   (inactive combo vs. genuinely sold-out non-preorder) and toasts «پیش‌خرید به
   سبد خرید اضافه شد» on preorder adds. The stock message now reads
   «پیش‌خرید؛ عرضه از {availableAt}؛ پس از عرضه ارسال می‌شود.» (the old copy
   said «پیش‌خرید تا …», which inverted the D4 meaning — `available_at` is the
   release/fulfilment date, not a preorder deadline; recorded per R15). The
   «پیش‌خرید» chip doubles as the purchasable-state badge and stays visible
   with a preorder combo selected, so a stock-0 preorder never renders the
   dead «ناموجود» chip. `data-testid="stock-message"` added for probing.
3. **`routes/cart.tsx` + `routes/checkout.tsx`** — «پیش‌خرید» chip
   (`bg-sage/25 text-sage-deep`) on preorder lines next to size/colour. The
   quote flow itself is untouched by design: `POST /stock/check` is the
   authority and already reports `ok:true` with prices for preorder lines
   (B4.13 mirrored checkout), so the cart neither blocks nor special-cases
   them.
4. **`lib/stock-issues.ts`** — `stockIssueMessage` lost its preorder branch:
   since B4.13 the server never reports a preorder line, so `not_available`
   now only ever means `coming_soon` («این محصول هنوز عرضه نشده…»). The stale
   copy claimed preorder was «فعلاً قابل سفارش نیست» — false since B4.13. The
   `product?` parameter was removed; the only caller (`cart.tsx`) updated.
   `stockIssueLabel` (checkout toasts) needed no change — it has no
   `not_available` preorder wording of its own.
5. **Order items** — «پیش‌خرید» chip from the payload flag `item.is_preorder`
   (additive field shipped with B4.13) in: customer «سفارش‌ها» list
   (`account.orders.tsx`), order detail (`account.order.$orderId.tsx`), and
   the admin `OrderDetailDrawer` items list. The printable invoice is
   deliberately untouched (money/status only, per its existing scope).

## Deliberate interpretation (recorded, per R15)

* **The preorder chip on product/cart/checkout is derived from catalog
  `product.availability`, the one on order items from `item.is_preorder`** —
  the flag frozen at purchase time. A product flipped to `in_stock` after the
  order therefore still shows the line as preorder in order views; that is the
  truthful history and matches the backend's fulfilment flag.
* **Deactivated variants stay blocked on preorder** — D4 removes the *stock*
  gate, not the activity gate; `availability_issue()` (B4.13) still rejects
  inactive variants, and the picker mirrors exactly that.
* **No preorder wording was added to the payment page** — money flow is
  identical for preorder and normal orders; the notification
  (`order_created_preorder`) already tells the customer the shipment follows
  the release date.

## Tests

No backend change → no backend test delta; `pytest` not rerun for this task
(backend untouched, last green at 396 in the AB-FE-06 session). Frontend
verification below; browser click-through stays OPEN (D10 gate — no
automation runtime).

## Verification

* `tsc --noEmit` — 0 errors.
* `eslint` on all 8 touched files — 0 errors; 2 pre-existing warnings in
  `OrderDetailDrawer` (the image-effect deps pattern, lines 194, untouched by
  this task). Prettier auto-fix applied to `VariantPicker.tsx`.
* `npm run build` — green (Node 22.23.2 via nvm; the known Node 20.9
  limitation).
* Grep sweep: `product.$id.tsx` retains the «پیش‌خرید» chip + badge label +
  `available_at` copy; `stock-issues.ts` no longer claims preorder is
  unorderable; `compare.tsx`/`shop.tsx` filter labels («پیش‌خرید») are correct
  as-is and untouched.

## What is NOT done / open

* **Browser click-through** — add-to-cart at stock 0 → cart chip → checkout →
  order chip can only be verified at build/type level here (D10 gate, no
  browser runtime). Left OPEN.
* The cart's stock-check "tolerance" needed no code (server already tolerates
  preorder lines since B4.13) — the task wording is satisfied by the existing
  backend contract plus the chip; recorded so nobody later "adds" a client-side
  preorder special-case that would diverge from the server.
* Product-card «پیش‌خرید» badges on `/shop` grid tiles were not in scope (the
  card shows availability via filter chips and compare; the product page is the
  purchase surface). Follow-up if merchandising wants tile-level preorder
  badges.

## Docs synced

`MASTER-BACKLOG.md` (JSON index F3.2c → DONE with audit + verification level,
`agent_start_task` → B2.5a, START HERE pointer, counts **54 DONE / 5 TODO of
59**, B4.13's «Open» line resolved), `frontend-tasks.md` (F3.2c checkbox + Done
paragraph), `feature-roadmap.md` (storefront preorder row), `session-log.md`,
this audit.
