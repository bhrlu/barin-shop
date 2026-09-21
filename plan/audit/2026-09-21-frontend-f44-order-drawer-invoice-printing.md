# Audit — 2026-09-21 — F4.4 order detail drawer + invoice printing (spec [FE-05])

## Task

**F4.4** from `plan/frontend-tasks.md`: the admin order detail drawer — `Sheet`
with the fulfilment stepper, customer address box with copy, itemised breakdown,
postal tracking input (F2.8) and an A4/A5 invoice print (the repo had **no print
stylesheet**).

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` §[FE-05] before starting.

- **Followed:** the spec's table columns remain (order number mono, customer,
  Persian date, total, payment/status badges via selects, «مشاهده و پردازش»
  action); `Sheet side="left"`; the four-step visual stepper (ثبت سفارش → تأیید
  پرداخت → در حال آماده‌سازی → تحویل به پست/پیک) with terracotta circles and the
  advance button; customer shipping box with «کپی آدرس گیرنده» + Sonner toast;
  itemised breakdown (name, color/size chips, quantity, subtotal); postal
  tracking field + save; «چاپ فاکتور رسمی» with `@media print` CSS so only the
  invoice prints — no nav, buttons or background colors.
- **Adapted (spec → live repo):**
  - Spec's step 2 is «تأیید پرداخت», but the live order lifecycle (Rule 4 —
    never change existing status strings) is `pending → processing → shipped →
    delivered`; the stepper maps to those with «در حال آماده‌سازی» as step 2.
    Payment confirmation stays the list's payment-status select.
  - Spec says "server-function mutations" — the repo's data layer is `api.ts` +
    React Query; `PATCH /orders/{id}` and `POST /orders/{id}/cancel` are used
    with cache invalidation, and the drawer's order object is re-resolved from
    the refetched list so it never goes stale.
  - Thumbnails are signed on demand via the existing `resolveImageUrls()` (B0.4
    images rule) — the spec assumed storage URLs were directly readable.

## What was done

**New `components/admin/OrderDetailDrawer.tsx`**
- Stepper: numbered terracotta circles with connector rails, done/active/pending
  states; advance button «تغییر وضعیت به …» (`NEXT_STATUS` map: pending →
  processing → shipped → delivered); cancelled shows a destructive notice,
  delivered shows a sage confirmation. Pending advances even when unpaid —
  status and payment are independent (matches the list behavior and backend).
- Receiver box: name/phone/address/postal code/method as a definition list, with
  the formatted-address copy button.
- Items: signed thumbnails, name, color/size/quantity, line total; totals block
  (subtotal, discount when > 0, shipping, grand total).
- Tracking input (F2.8) — pre-filled, saves via `PATCH /orders/{id}`, empty
  clears; also a «لغو سفارش» action via the existing cancel endpoint.
- Print invoice: the invoice DOM is **portalled to `<body>`** as
  `#__se_invoice_root`; screen CSS hides that node, and the print block shows it
  as the whole page (SÂNDÉ header, order/payment info, buyer box, bordered items
  table, grand total, footer note) with `@page A4; margin: 14mm`.

**`styles.css`** — global print block: while the drawer is open,
`body[data-order-print-open="true"]` hides everything except `#__se_invoice_root`;
the portal (and the body attribute) exist only while the drawer is open, so
`Ctrl+P` anywhere else prints normally.

**`admin.orders.tsx`** — added «مشاهده و پردازش» (Eye icon, terracotta pill)
per order; opens the drawer. List keeps status/payment selects, tracking input
and copy-address; mutation invalidation extended to the KPI queries the shell
badges and dashboard read.

## Files changed

- `vogue-vintage-vibes/src/components/admin/OrderDetailDrawer.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.orders.tsx` (rewired)
- `vogue-vintage-vibes/src/styles.css` (print block)
- `vogue-vintage-vibes/DESIGN_SYSTEM.md` (§3.3 [FE-05] row, notes 5 and 8)
- `plan/frontend-tasks.md`, `plan/feature-roadmap.md`, `plan/README.md`,
  `plan/session-log.md`, `vogue-vintage-vibes/FEATURES.md`

## How to verify

```bash
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build
```

Manual (stack up, admin logged in): `/admin/orders` → «مشاهده و پردازش» →
stepper shows the order's current stage → advance it (list + dashboard update)
→ copy address → save/clear tracking → «چاپ فاکتور رسمی» → print preview shows
only the invoice (A4, no chrome). Close the drawer and `Ctrl+P` → normal page
print.

## What is NOT done / open

- Spec's «تأیید پرداخت» step label intentionally not used (Rule 4 lifecycle);
  payment status confirmation stays in the list select — a pay-toggle inside the
  drawer could be added later if the user wants it.
- Invoice carries the store header + order data only — no company registration/
  tax-ID fields (no data model for them; would need a spec/user decision).
- Print typography uses the repo's normal fonts; the spec's A5 variant and a
  dedicated print type scale were not built (A4 only, standard scale).
- No smoke/pytest changes — frontend-only task; all endpoints used already
  have live coverage (156 checks).
