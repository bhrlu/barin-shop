# Frontend Task List (vogue-vintage-vibes/)

Legend: `[ ]` todo · `[x]` done (audit file required) · audit links in `plan/audit/`

## Milestone F1 — Wire the store to the Python backend

**Cut-over decision (user, Session 6): full switch.** Every Supabase import is
replaced by `src/lib/api.ts`, which talks straight to the FastAPI backend. The
list below is the **resumable tracker**: tick an item, add its audit link, and a
new session can pick up exactly where this one stopped. Legend: `[ ]` todo ·
`[~]` in progress · `[x]` done.

### F1 progress tracker (resumable)

- [x] **F1.0 Backend endpoints for the switch** — `PATCH /auth/me` (profile save)
  and `GET /payments/mine` (customer payment history) added; `POST /checkout`,
  `POST /coupons/validate`, `GET /orders`, `POST /orders/{id}/payment-session`,
  `POST /orders/{id}/payment-complete`, `POST /orders/{id}/cancel`, `/addresses`,
  `/favorites`, `/admin/*`, `/storage/upload-url`, `/storage/sign` already existed.
  → audit: [2026-09-19-seed-and-frontend-switch.md](audit/2026-09-19-seed-and-frontend-switch.md)
- [x] **F1.0b Catalog seed** — `backend/app/seed_products.py` (20 products,
  idempotent) + `backend/app/seed_demo.py` (demo addresses/favorites/orders for
  `customer@sande.local`), both wired into the compose `db-init` job.
  → audit: same file as F1.0
- [x] **F1.1 Backend client module** — `src/lib/api.ts` extended into the single
  data layer: token storage, `request()` with `ApiError`, and a typed method per
  endpoint (auth, catalog, checkout, coupons, orders, payments, addresses,
  favorites, admin, storage).
  → audit: same file as F1.0
- [x] **F1.1b Auth/session layer** — `src/lib/auth.tsx` rewritten around the
  backend JWT (no Supabase `Session`/`User`); `_authenticated/route.tsx` guard,
  `src/routes/auth.tsx` sign-in/sign-up, `start.ts` (Supabase auth-attacher
  removed), Google OAuth removed (backend has no OAuth).
  → audit: same file as F1.0
- [x] **F1.1c Catalog + images** — `src/lib/catalog.ts` reads `GET /products` and
  signs `uploads/…` paths via `POST /storage/sign`; `ProductImageManager` uploads
  through `POST /storage/upload-url`.
  → audit: same file as F1.0
- [x] **F1.2 Real coupons in cart** — hardcoded `SANDE10` in `src/routes/cart.tsx`
  replaced by `POST /coupons/validate`; applied code passed to checkout in
  `sessionStorage` (never the amount).
  → audit: same file as F1.0
- [x] **F1.3 Checkout through backend** — `src/routes/checkout.tsx` calls
  `POST /checkout` (stock-validated, server-priced, coupon applied);
  `stock_conflict` issues surface in the UI.
  → audit: same file as F1.0
- [x] **F1.4 Payment page on the backend** — `payment.$orderId.tsx` uses
  `GET /orders/{id}/payment-session` + `POST /orders/{id}/payment-complete`
  (backend's simulated gateway, same UX as before). Real Zarinpal redirect flow
  remains open (A1 below).
  → audit: same file as F1.0
- [x] **F1.5a Account routes** — orders, order detail, addresses, favorites,
  payments, profile all on the backend (`/orders`, `/addresses`, `/favorites`,
  `/payments/mine`, `PATCH /auth/me`).
  → audit: same file as F1.0
- [x] **F1.5b Admin routes** — dashboard stats, orders (+status patch), products
  CRUD, users on `/admin/*` and `/products`.
  → audit: same file as F1.0
- [x] **F1.8 Remove Supabase from the frontend** — `src/integrations/supabase/*`,
  `src/integrations/lovable/*`, `order-actions.functions.ts` and
  `payment.functions.ts` deleted; no `@supabase/supabase-js` import remains
  (package.json entry left in place to avoid churning the lockfile).
  → audit: same file as F1.0
- [x] **F1.10 End-to-end run on the Docker stack** — stack rebuilt + seeded;
  a full login → catalog → checkout → payment pass on the live backend, plus
  frontend SSR/module/CORS checks. Found and fixed the checkout `HTTPException`
  bug (B3.8). No headless-browser click-through yet.
  → audit: [2026-09-19-e2e-flow-docker.md](audit/2026-09-19-e2e-flow-docker.md)

### F1 still open (nice-to-have / blocked)

- [x] **F1.5 Search bar** — header search opens `GET /search` results (dropdown or
  `/shop?q=`), wired in `SiteHeader.tsx` + `shop.tsx` query param. Done as F3.1.
  → audit: [2026-09-20-frontend-f31-search.md](audit/2026-09-20-frontend-f31-search.md)
- [x] **F1.6 Live stock in product page & cart** — per-combination stock on the
  product page (F3.2) plus a `POST /stock/check` re-validation of the whole cart
  on open/edit (F3.5), with per-line issues and a blocked checkout.
  → audit: [2026-09-21-frontend-f35-f36-cart-stock-admin.md](audit/2026-09-21-frontend-f35-f36-cart-stock-admin.md)
- [x] **F1.7 Stock decrement shown to admin** — the admin product list reads
  `useCatalog()` (refetched on focus and invalidated by every admin mutation) and
  F3.6 added an explicit live view: `/admin/inventory` counters + low-stock report
  and per-variant stock in the variant editor.
  → audit: same file as F1.6
- [ ] **F1.9 Lovable preview tooling** — `reportLovableError`/`error-capture` kept
  (no Supabase dependency); revisit once the app runs outside Lovable.

### A1 — open decisions

- **Real Zarinpal redirect** in the payment page (`POST /payments/start` → gateway
  → `?verify=…` return route) instead of the backend's simulated gateway.
- **Google / OAuth login** is gone with Supabase; needs a backend OAuth flow or a
  third-party auth provider before it can return.

## Milestone F2 — Gaps from FEATURES.md part 6 (in progress — F2.1, F2.7 done)

> ℹ️ The Supabase-vs-backend blocker that used to sit here is resolved: Session 6
> cut the whole frontend over to the FastAPI backend (see the F1 tracker).- [x] **F2.1 Contact form persistence** — the form is real now: controlled inputs,
  `api.contact()` → `POST /contact` (which stores the message), min-length
  attributes matching the API, Persian success/error toasts. Backend in B3.9.
  → audit: [2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md](audit/2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md)
- [x] **F2.1b Admin contact inbox** — new `/admin/messages` tab: filter chips
  (همه / پاسخ‌داده‌نشده / پاسخ‌داده‌شده), Persian Jalali dates, copy-to-clipboard on
  the sender's contact, mark answered/reopen and delete. Backend: a
  `PATCH /admin/contact-messages/{id}` endpoint was added for the answered flag
  (new smoke assertions cover mark/filter/422).
  → audit: [2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md](audit/2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md)
- [x] **F2.4 Admin refund-requests page** — new `/admin/refunds` tab: tabs
  (در انتظار بررسی / تسویه‌شده / همه) per spec [FE-06], claim cards with the
  reason in the terracotta-edge quote box, claimant name/email, and a
  `RefundActionDialog` (approve / reject / settle) wired to `PATCH /refunds/{id}`
  (settle flips the order's payment status server-side). Settlement requires the
  Paya/Satna bank tracking code (backend enforces it since B5.3) and settled
  cards show the code + settlement date.
  → audit: same file as F2.1b; bank-code UI in [2026-09-21-backend-b53-refund-bank-tracking.md](audit/2026-09-21-backend-b53-refund-bank-tracking.md)
- [x] **F2.3 Forgot password** — **backend work needed** (this line used to say
  "Supabase reset email flow"; there is no Supabase any more and `auth.py` has no
  reset endpoint). Add a reset-token endpoint + email to `backend-tasks.md` first,
  then the UI. B2.1 (DONE) provides the email transport: add an email-only entry
  point to `backend/app/services/notifications.py` (never call
  `SmtpEmailProvider` directly). SMTP is unconfigured, so decide how the reset
  link is verified without real delivery before building.
  Done (2026-09-23): `password_reset_tokens` (hash-only, 30 min, one-time,
  superseded by a newer link, ≤3/hour), `POST /auth/password/forgot` (identical
  202 for every address) + `/reset`, email via `notifications.queue_private_email`
  (not sent while SMTP is unconfigured — no dev link shortcut), `/forgot-password`,
  `/reset-password`, link on `/auth`. Browser tested 20/20 + clean environment.
  → audit: [2026-09-23-f23-forgot-password.md](audit/2026-09-23-f23-forgot-password.md)
- [x] **F2.5 Pagination for shop & admin lists** — envelope pagination
  (`{items,total,page,page_size,pages}`, bare list without `?page=`) on
  `/products`, `/orders`, `/admin/{orders,users,payments,contact-messages,reviews}`
  + `offset` on audit-logs; shared `Pager` component on shop (URL `?page=`),
  admin orders/users/messages/reviews and account orders. Also fixed a live
  500: `/products` with a token crashed on string-vs-set roles.
  → audit: [2026-09-22-f25-pagination-everywhere.md](audit/2026-09-22-f25-pagination-everywhere.md)
- [x] **F2.6 Charts for admin dashboard** — `/admin` now has a range selector
  (امروز/۷/۳۰/همه), four KPI cards with delta badges, a recharts revenue area
  chart, an order-status donut with legend, an amber urgent-actions callout, and
  the latest-orders list — all fed by `GET /admin/kpis?range=` (B5.2).
  → audit: [2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md](audit/2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md)
- [x] **F2.7 Default address in checkout** — saved addresses are offered above the
  shipping box (default pre-selected, «آدرس جدید» clears it) and pre-fill
  name/phone/province/city/address/postal code; the account tab shows a «پیشفرض»
  badge, can move the flag, and can create an address as default. Backend
  (`PATCH /addresses/{id}` + single-default invariant) in B3.10.
  → audit: [2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md](audit/2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md)
- [x] **F2.7b Edit a saved address** — each card has a «ویرایش» action that opens an
  inline pre-filled form (shared `AddressFields` with the create form, unique ids via
  a `prefix`), saving with a **fields-only** patch so an edit can never move the
  default flag. Smoke asserts `PATCH fields only edits without touching is_default`.
  → audit: [2026-09-21-frontend-f27b-edit-address.md](audit/2026-09-21-frontend-f27b-edit-address.md)
- [x] **F2.8 Shipment tracking number** — admin enters the postal/courier code in
  the order row (F2.8 input in `admin.orders.tsx`, saved via `PATCH /orders/{id}`;
  empty input clears it), and the customer order page shows «کد رهگیری مرسوله» in
  the stepper box. Backend: additive `orders.tracking_code` column (`TRACKING_DDL`)
  + PATCH support; the payment-session `tracking_code` is unrelated and unchanged.
  → audit: same file as F2.1b

## Milestone F3 — Catalog & Products UI (backend API ready)

The catalog/product **backend API is complete and smoke-verified** — see
[audit/2026-09-20-catalog-backend-and-address-fix.md](audit/2026-09-20-catalog-backend-and-address-fix.md)
and `plan/feature-roadmap.md`. This milestone wires it into the UI. Nothing here
needs new backend work except where explicitly noted.

### F3.0 API client + types (blocking prerequisite) — DONE

→ audit: [2026-09-20-frontend-f30-api-client.md](audit/2026-09-20-frontend-f30-api-client.md)

- [x] Extend the `Product` type in `src/lib/api.ts` with `tags`, `badge`,
  `availability`, `available_at`, `low_stock_threshold`, `avg_rating`,
  `review_count`
- [x] Extend `api.products()` params with `tag`, `badge`, `availability`,
  `on_sale`, `size`, `color`, `min_price`, `max_price`, `sort`
- [x] Add client methods for: `GET /products/{id}`, `/products/{id}/related`,
  `/recommendations`, `/products/compare`, `/products/{id}/variants`,
  `/products/{id}/reviews` (GET/POST), `POST /products/{id}/view`,
  `GET /recently-viewed`, `GET /search/suggest`, `GET/DELETE /search/history`
- [x] Add admin client methods: `GET /admin/inventory`,
  `/admin/inventory/low-stock`, `GET /admin/reviews`, `PATCH /reviews/{id}`,
  variant CRUD (`POST /products/{id}/variants`, `PATCH/DELETE /variants/{id}`)
- [x] Bucket + rating fields added to `Product`; new types exported:
  `Availability`, `ProductBadge`, `ProductSort`, `ProductListParams`,
  `ProductVariant(-Input)`, `Review`, `ReviewList`, `ReviewInput`,
  `SearchSuggestion`, `SearchHistoryEntry`, `InventorySummary`,
  `LowStockProduct`, `LowStockVariant`, `LowStockReport`
- [x] Bridged the legacy `@/data/products` `Product` type and `toProduct()` in
  `@/lib/catalog` to the new catalog fields (`tags`, `badge`, `availability`,
  `availableAt`, `lowStockThreshold`, `avgRating`, `reviewCount`), so
  `useCatalog()` consumers can read them.
  → audit: [2026-09-20-frontend-catalog-type-bridge.md](audit/2026-09-20-frontend-catalog-type-bridge.md)

### F3.1 Search — DONE

→ audit: [2026-09-20-frontend-f31-search.md](audit/2026-09-20-frontend-f31-search.md)

- [x] Header search box in `SiteHeader.tsx` (search icon exists, no behaviour yet)
  with a debounced `GET /search/suggest` dropdown
  (products / categories / tags / recent queries) — new `HeaderSearch.tsx`,
  images signed via `resolveImageMap`, ArrowUp/Down + Enter navigation
- [x] Search history: show recent searches in the dropdown, clear-all and
  per-entry delete (signed-in only, `sonner` error toasts)
- [x] `shop.tsx` accepts `?q=` and calls `GET /search`; result count + empty state
  (loading/error/empty states; `CatalogPage` split out so a search never fetches
  the whole catalog)
- [x] **F3.1b Tags in `/search`** — the backend matcher now covers `tags` too
  (`tag_hit` ranking: name > category > tag > description/material) and the
  starter catalog is tagged, so tag suggestions return products.
  → audit: [2026-09-20-backend-search-tags.md](audit/2026-09-20-backend-search-tags.md)

### F3.2 Product page (`product.$id.tsx`) — DONE

→ audit: [2026-09-20-frontend-f32-product-page.md](audit/2026-09-20-frontend-f32-product-page.md)

- [x] Variant picker from `GET /products/{id}/variants` — disable unavailable
  size×color combos, show per-combination stock ("N left"), block add-to-cart at 0
  (`components/product/VariantPicker.tsx` + `lib/variants.ts` mirroring the
  backend rule)
- [x] Reviews section: stars summary, rating distribution, list, and a write/edit
  review form (`GET/POST /products/{id}/reviews`)
  (`components/product/ReviewsSection.tsx`, incl. delete-own-review and seller replies)
- [x] Related products carousel (`GET /products/{id}/related`)
- [x] Recommended products carousel (`GET /products/{id}/recommendations`)
  (both via `components/product/ProductRail.tsx`, RTL embla rail)
- [x] Record a view on mount (`POST /products/{id}/view`)
- [x] Availability states: badge + `coming_soon`/`preorder` with `available_at`;
  disable add-to-cart / show "به‌زودی"
- [x] Show `tags` and `badge` (special offer / new)
- [x] Single-product fetch → the page now uses `GET /products/{id}` instead of
  reading the whole catalog (`useCatalog().byId`)
- [x] **F3.2b Availability is UI-only** — fixed in the API: `coming_soon` and
  `preorder` are rejected by `POST /stock/check` and checkout with reason
  `not_available` (B4.11).
  → audit: [2026-09-21-backend-b411-b412-availability-multifacet.md](audit/2026-09-21-backend-b411-b412-availability-multifacet.md)

### F3.3 Catalog listing / shop (`shop.tsx`, `ProductCard.tsx`) — DONE

→ audit: [2026-09-20-frontend-f33-shop-filters-compare.md](audit/2026-09-20-frontend-f33-shop-filters-compare.md)

- [x] Move filtering + sorting to the server via the new `api.products()` params
  (replaces the client-side `useMemo` filter) — the URL (`validateSearch`) is the
  single source of truth; sort options now new/popular/rating/price_asc/price_desc
- [x] Add filter chips for availability, tag, badge and on-sale
  (tag chips come from the cached catalog — no tag-facet endpoint yet)
- [x] Rating display on `ProductCard` (`avg_rating` / `review_count`)
- [x] Compare: add-to-compare toggle + `/compare` page using
  `GET /products/compare?ids=` (`lib/compare.tsx` + `CompareBar`, localStorage,
  cap 4; new route added to `routeTree.gen.ts`)
- [x] **F3.3b card structure** — `ProductCard` root became a wrapper div so the
  compare toggle is not a `<button>` inside the product `<a>`
- [x] **F3.3c multi-select size/color** — the sidebar chips now toggle, the URL
  carries repeated values (`?size=M&size=L`) and `api.products()` sends them
  repeatedly; B4.12 accepts both shapes.
  → audit: same file as F3.2b

### F3.4 Recently viewed — DONE

→ audit: [2026-09-20-frontend-f34-recently-viewed.md](audit/2026-09-20-frontend-f34-recently-viewed.md)

- [x] "بازدیدهای اخیر" rail on home/shop (`GET /recently-viewed`) — new
  `components/product/RecentlyViewedRail.tsx` reusing `ProductRail`; renders only
  for signed-in customers with a non-empty list
- [ ] **F3.4b Guest recently-viewed** — the endpoint needs auth, so signed-out
  browsing is not remembered; decide whether a localStorage rail should merge
  with the account list after sign-in (`GET /recently-viewed` has no DELETE either)

### F3.5 Cart (`cart.tsx`) — DONE

→ audit: [2026-09-21-frontend-f35-f36-cart-stock-admin.md](audit/2026-09-21-frontend-f35-f36-cart-stock-admin.md)

- [x] Wire `POST /stock/check` on add-to-cart / cart open; surface per-line issues
  and per-variant availability — `api.stockCheck()` now posts the bare array the
  backend expects (the old `{lines:…}` body was a dormant 422), the query is keyed
  on the full cart signature so every edit re-validates, and checkout is blocked
  while `ok: false`. Add-to-cart keeps the variant-aware local rule (F3.2).
- [x] **F3.5b Re-check on focus** — a cart left open keeps its last result until an
  edit (checkout still re-validates server-side, so this is stale UI only)
  Done (2026-09-23): The cart page re-runs `POST /stock/check` on window `focus` (React Query already covered tab switches via `visibilitychange`); `cancelRefetch: false` keeps a tab switch at one request and an empty cart never posts. 15 browser checks; negative controls: old file 4 fail, no dedupe 1 fails, no guard 1 fails. Browser tested.
  → audit: [2026-09-23-f35b-cart-stock-recheck-on-focus.md](audit/2026-09-23-f35b-cart-stock-recheck-on-focus.md)

### F3.6 Admin — DONE

→ audit: same file as F3.5

- [x] Product editor (`admin.products.tsx`): fields for `tags`, `badge`,
  `availability`, `available_at`, `low_stock_threshold` (+ list chips for
  availability/badge/موجودی کم)
- [x] Variants editor per product (create / patch stock / delete) —
  `components/admin/VariantEditor.tsx`, opened per row from the products list
- [x] Inventory / low-stock screen (`GET /admin/inventory`,
  `/admin/inventory/low-stock`) — new `/admin/inventory` route + tab
- [x] Reviews moderation screen: hide/publish + seller reply (`GET /admin/reviews`,
  `PATCH /reviews/{id}`) — new `/admin/reviews` route + tab

### F3.7 Supersedes open F1/F2 items

- [x] F1.5 search bar → covered by F3.1
  → audit: same file as F3.1
- [x] F1.6 live stock in product page & cart → covered by F3.2/F3.5
  → audit: same file as F3.5
- [x] F2.2 reviews & ratings → storefront UI is F3.2, admin moderation is F3.6
  → audit: same file as F3.5

## Milestone F4 — Spec-aligned admin UI (from `design/SANDE_FULL_DEV_SPEC.md`)

The spec's Part B3 describes a sidebar-shell back-office with a data grid, detail
drawer, refunds and coupon screens. §3.3 of `vogue-vintage-vibes/DESIGN_SYSTEM.md`
maps what exists today; these are the pieces with no task yet. Read the spec first
(Rule 0) and follow its design rules — but the repo's data layer and routing win on
conflict (DESIGN_SYSTEM.md §5).

- [x] **F4.1 Token-driven status badges** — one `StatusBadge` using the status
  semantics table (DESIGN_SYSTEM.md §2.3 + §7.2) for order/payment/refund state,
  replacing the uniform terracotta/sand chips; label always names the status, colour
  is secondary. Spec B0.2/B4.2. Done (F4.1): `components/StatusBadge.tsx` built
  from the §7.2 snippet (+ `succeeded`/`failed`/`new` tones); converted account
  orders, admin refunds/orders/dashboard and the order drawer; unknown statuses
  degrade to brand tone with the raw label.
  → audit: [2026-09-21-b51a-audit-ip-f41-status-badges.md](audit/2026-09-21-b51a-audit-ip-f41-status-badges.md)
- [x] **F4.2 Admin shell** — sidebar layout (`[FE-01]`): right `w-64` sidebar with
  lucide icons, active terracotta edge, mobile sheet, topbar with breadcrumbs +
  quick search + role badge, replacing the tab bar in `admin.tsx`. Spec B3/[FE-01].
  Done (F4.2): sticky topbar (quick search → `/shop?q=`, role badge, logout),
  desktop sidebar card + mobile Sheet, 18px icons, active tint, KPI-fed badges on
  orders/refunds; **tabs are role-gated** per B5.4 (`ROLE_TAB_KEYS` mirrors
  backend capabilities — support sees داشبورد/پیام‌ها/نظرات only, order_manager
  adds fulfillment). Breadcrumbs/avatar/command-palette deferred — see audit.
  → audit: [2026-09-21-frontend-f42-admin-shell-role-gating.md](audit/2026-09-21-frontend-f42-admin-shell-role-gating.md)
- [ ] **F4.3 Reusable admin data grid** (`[FE-02]`) — search, filter chips, sort,
  pagination, bulk actions, copy-to-clipboard for tracking codes/phones. Needs a
  **decision to install `@tanstack/react-table`**; overlaps F2.5 (pagination).
  The export buttons for `/admin/export/*.{csv,xlsx}` (B2.2) shipped on their
  own in AB-FE-02 (`components/admin/ExportControls.tsx`); when the grid is
  built, its toolbar can host them.
- [x] **F4.4 Order detail drawer + invoice printing** (`[FE-05]`) — `Sheet` with the
  fulfilment stepper, customer address box with copy, itemised breakdown, postal
  tracking input (F2.8) and a `@media print` A4/A5 invoice (no print stylesheet
  exists yet).
  Done (F4.4): `OrderDetailDrawer.tsx` — left Sheet, 4-step terracotta stepper on
  the live `pending → processing → shipped → delivered` lifecycle, receiver box +
  copy, signed item thumbnails + totals, tracking field, cancel; «چاپ فاکتور
  رسمی» portals the invoice to `<body>` and the new `styles.css` print block
  prints only it (A4, no chrome). Spec's «تأیید پرداخت» step label adapted to the
  live statuses (Rule 4) — see audit.
  → audit: [2026-09-21-frontend-f44-order-drawer-invoice-printing.md](audit/2026-09-21-frontend-f44-order-drawer-invoice-printing.md)
- [x] **F4.5 Coupons manager** (`[FE-07]`) — ticket-style cards, usage progress,
  active toggle, Jalali date pickers on top of the existing `/coupons` CRUD.
  Done (F4.5): `/admin/coupons` with filter chips, ticket cards (copy code,
  Switch toggle, usage bar red at 100%), create/edit dialog (percent XOR amount,
  mirrors backend), delete + code generator; new backend `DELETE /coupons/{id}`
  (audited). Date picker is the native input (no Persian calendar dependency) —
  see audit. Customer-side refunds page stays **F2.4**; charts stay **F2.6**.
  → audit: [2026-09-21-b61-state-machine-f45-coupons-manager.md](audit/2026-09-21-b61-state-machine-f45-coupons-manager.md)

## Audit follow-ups (2026-09-22 full-stack audit)

- [x] **F5.1 Admin route role guard** (`[FE-01]`.3) — hiding a tab was not a
  guard: a staff member who typed `/admin/users` still got the page plus a silent
  403 and its empty state. The shell now maps the path to its tab and shows a
  Persian permission notice for roles that lack it.
- [x] **F5.2 Persian 404 and error boundary** (B1.4) — the root
  `notFoundComponent` / `errorComponent` were still the English Lovable scaffold.
- [x] **F5.3 Staff role labels in `/admin/users`** — every role other than
  `admin` rendered as «مشتری», so the `support` and `order_manager` accounts
  looked like customers.
- [x] **F5.4 `bun run lint` green** — 45 prettier errors fixed with
  `bun run format` (source files only).
  → audit for F5.1–F5.4: [2026-09-22-full-stack-audit-and-fixes.md](audit/2026-09-22-full-stack-audit-and-fixes.md)
- [x] **F5.5 Audit-log viewer** — `GET /admin/audit-logs` shipped with B5.1 but
  had no UI and no `api.ts` client method. Now `/admin/audit` (admin /
  super_admin only): action / entity / staff / entity-id filters, 25-row offset
  paging, Jalali timestamp, IP, old→new value table, loading / empty / error
  states; `api.adminAuditLogs()` + `formatFaDateTime()`. Browser tested.
  → audit: [2026-09-22-f55-audit-log-viewer.md](audit/2026-09-22-f55-audit-log-viewer.md)
- [x] **F5.6 Role management UI** (`[FE-08]`) — `PUT /admin/users/{id}/roles`
  existed and was audited; the users page was read-only. Now each row has a
  «نقش‌ها» dialog (disabled on your own row): pick `super_admin` /
  `order_manager` / `support`, then review the +/− diff and type the user's email
  to confirm. Legacy roles are read-only. `api.adminSetUserRoles()`. Browser tested.
  → audit: [2026-09-22-f56-role-management-ui.md](audit/2026-09-22-f56-role-management-ui.md)
- [x] **F5.7 Split the admin chart bundle** — recharts (~553 kB raw) and lodash
  (~164 kB) are pulled into the shared bundle for the dashboard alone.
  Done (2026-09-23): Measured, no code change: recharts and lodash (transitive, via recharts) live only in the dashboard's route chunk (`admin.index-*.js`, 405.7 kB / 106.3 kB gzip), preloaded only for `/admin`; `/`, `/shop`, `/admin/orders`, `/admin/products` load no chart code. An in-route lazy split was built and measured on the production build (throttled): KPIs 3616→4432 ms, charts 3713→4756 ms, so it was reverted. Level: measured (production build).
  → audit: [2026-09-23-f57-admin-chart-bundle-measurement.md](audit/2026-09-23-f57-admin-chart-bundle-measurement.md)
- [x] **F5.8 `/shop` fetches the catalog twice** — `catalogQuery`
  (`?include_inactive=true`) and the filtered list query both run on every visit.
  Done (2026-09-23): `/shop` builds its filter options from the new public `GET /products/facets` (sizes, colours, tags, price range of the active catalogue) instead of downloading every product; normal/filtered visits = facets + one page request, search = `/search` only. 5 backend tests (mutation controls), smoke 231/0, 23 browser checks (negative control: 6 fail on the old code). Browser tested.
  → audit: [2026-09-23-f58-shop-facets-endpoint.md](audit/2026-09-23-f58-shop-facets-endpoint.md)
- [x] **F5.9 Coupon discount-cap field in the admin dialog** (`NEW-ABBE03-1`,
  discovered during AB-BE-03) — the backend now stores and enforces
  `coupons.max_discount_cap`, but `admin.coupons.tsx` and the `AdminCoupon` /
  `adminCreateCoupon` / `adminUpdateCoupon` types in `src/lib/api.ts` do not
  mention it, so a ceiling can only be set through the API. Sending `0` on the
  PATCH clears it.
  Done (2026-09-23): cap field in the coupon dialog (percent coupons only; 0 clears on edit), shown on the card; the page now imports the canonical `AdminCoupon` type. Browser 14/14 incl. the real discount via `/coupons/validate`.
  → audit: [2026-09-23-f59-coupon-cap-field.md](audit/2026-09-23-f59-coupon-cap-field.md)
- [ ] **F5.10 Customers see staff nav tabs in the admin shell** (`NEW-F56-2`,
  discovered during F5.6) — a signed-in customer on `/admin/*` gets the "no admin
  access" notice, but the sidebar still lists داشبورد / پیام‌ها / نظرات because
  `admin.tsx` falls back to `ROLE_TAB_KEYS["support"]` for any unknown role. No
  data leaks (every call is gated), but the nav should be empty for non-staff.
- [x] **AB-FE-02 Admin export controls** (`[FE-02]` export + `[BE-08]`, from the
  Master Backlog) — B2.2's exports had no UI. `/admin/orders` now has a panel:
  inclusive local date range + order status → «خروجی CSV» / «خروجی Excel», plus a
  collapsible sales report (best-sellers, daily). `/admin/products` has catalog
  CSV/Excel buttons. Files are authenticated blob downloads through
  `api.ts::requestFile()` and keep the server's RFC-6266 Persian filename; the
  backend now exposes `Content-Disposition` via CORS. Loading, validation and
  Persian error states. Browser tested.
  → audit: [2026-09-22-abfe02-admin-export-controls.md](audit/2026-09-22-abfe02-admin-export-controls.md)
- [x] **AB-FE-05 Admin products server pagination** (from `[FE-04]`, completes
  F2.5) — `/admin/products` no longer renders the whole `useCatalog()` list. It
  reads 20-row pages of `GET /products?include_inactive=true` under its own
  `["admin-products"]` key, with URL-driven `?page=&category=&availability=`
  (filters survive paging; any filter change resets the page), the server total,
  the shared `Pager`, skeleton/error/empty states, and an out-of-range page →
  last page. Save, delete and variant changes invalidate it. Browser tested.
  → audit: [2026-09-22-abfe05-admin-products-pagination.md](audit/2026-09-22-abfe05-admin-products-pagination.md)
- [ ] **F5.11 `/shop` leaks invalid URL params to the API** (`NEW-ABFE05-2`,
  discovered during AB-FE-05) — TanStack Router merges a route's validated search
  over the parent's raw one, so keys `validateSearch` *omits* survive raw:
  `/shop?page=abc` sends `page=abc` (422, retried 3×, no products) and
  `?category=hack` filters on it. Return rejected keys as explicit `undefined`
  (the AB-FE-05 fix in `admin.products.tsx`).
- [x] **F5.12 Cart provider loads the whole catalogue on every route**
  (`NEW-ABFE05-3`, discovered during AB-FE-05) — `CartProvider` in `__root.tsx`
  runs `catalogQuery` (all products, `include_inactive=true`) on every page, admin
  pages included, to price and stock-check the cart. Fetch only the cart's products
  (or defer until the cart is used). Related to F5.8 but broader.
  Done (2026-09-23): `CartProvider` no longer queries the catalogue; the display subtotal moved to `useCartSubtotal()`, called only by `/cart` and `/checkout`. Admin and other storefront routes make 0 catalogue requests (was 1 each); cart, coupon, stock-issue and checkout flows re-tested (27 browser checks; negative control: 6 fail on the old code). Browser tested.
  → audit: [2026-09-23-f512-cart-provider-no-catalog.md](audit/2026-09-23-f512-cart-provider-no-catalog.md)

- [x] **B2.1 (frontend part) Notification centre + admin notification settings**
  — delivered with backend task B2.1: header bell (`NotificationBell` in
  `SiteHeader`, unread badge, latest-6 popover, mark-all-read, links to the order),
  `/account/notifications` (all/unread filter, per-item read, pager) and
  `/admin/settings` (admin/super_admin; locked-on in-app switch + SMS/email
  switches with provider state). Also fixed the shared `ui/switch.tsx` thumb,
  which slid out of its track under RTL. Browser tested.
  → audit: [2026-09-22-b21-notification-infrastructure.md](audit/2026-09-22-b21-notification-infrastructure.md)
- [x] **F5.14 Admin coupon create / edit / toggle all fail with 422** (`NEW-B21-5`,
  discovered during B2.1) — `api.adminCreateCoupon` and `api.adminUpdateCoupon`
  pass a raw `body: JSON.stringify(…)`, but `request()` sets
  `Content-Type: application/json` only on the `json:` path, so the browser sends
  `text/plain` and FastAPI 0.141 answers 422 («Input should be a valid
  dictionary…»). Verified: the same body is 200 as `application/json`, 422 as
  `text/plain`. Every save and every «فعال» switch on `/admin/coupons` is
  silently rejected. Fix: pass `json:` in both methods; add a browser check.
  Done (2026-09-22): both methods use `json:`; browser tested 14/14 (create,
  toggle off/on, edit, delete, error paths).
  → audit: [2026-09-22-f514-coupon-json-body.md](audit/2026-09-22-f514-coupon-json-body.md)
- [x] **F5.16 Coupon edit dialog cannot clear expiry / total cap / discount kind**
  (`NEW-F514-1`, discovered during F5.14) — the dialog sends `null` for an emptied
  field and `PATCH /coupons/{id}` treats `null` as "unchanged" (observed: clearing
  the expiry keeps the old date; a percent coupon switched to a fixed amount keeps
  `percent_off`; `max_uses` cannot be cleared at all). Define clear semantics in
  `CouponUpdate`, send them from the dialog; pytest + browser.
  Done (2026-09-23): `expires_at: ""` / `max_uses: 0` clear; a kind switch clears
  the other kind (both → 422) — the old row kept `percent_off`, so a switch to a
  fixed amount never reached checkout. 7 pytest + dialog 15/15.
  → audit: [2026-09-23-f516-coupon-edit-clear-and-kind.md](audit/2026-09-23-f516-coupon-edit-clear-and-kind.md)
- [x] **F5.15 A failed `/auth/me` signs the user out** (`NEW-B21-6`, discovered
  during B2.1) — `AuthProvider.refresh()` calls `setToken(null)` on *any* error,
  not only a 401: a network error, a backend restart or a full-page navigation
  that interrupts the request drops a valid session (reproduced: token gone after
  quick successive page loads, identical without the B2.1 bell). Clear the token
  only on 401/403; keep it and retry otherwise.
  Done (2026-09-23): cleared only on 401/403/404; otherwise kept with retries at
  1 s / 3 s / 10 s. Browser tested 16/16 (negative control against the old code:
  4 failures). → audit: [2026-09-23-f515-auth-refresh-keeps-session.md](audit/2026-09-23-f515-auth-refresh-keeps-session.md)
- [x] **F5.13 Guest direct-load of a protected route logs a hydration mismatch**
  (`NEW-B21-4`, discovered during B2.1) — opening e.g. `/account/payments` signed
  out renders the `ssr: false` route on the server, then `_authenticated`'s
  client `beforeLoad` redirects to `/auth?redirect=…` and React reports «Hydration
  failed … server rendered HTML didn't match the client» (page error; the tree is
  regenerated, nothing breaks visibly). Pre-existing: identical with the
  notification bell removed. Redirect without a mismatching first render.
  Done (2026-09-23): `beforeLoad` resolves `{ user: null }`; the layout redirects
  once after mount to the URL captured on first render. 7 → 0 hydration failures;
  browser tested (20/20 + 58/58 + 16/16 + 54/54).
  → audit: [2026-09-23-f513-guard-redirect-after-mount.md](audit/2026-09-23-f513-guard-redirect-after-mount.md)

## Rules reminder

Every completed F-task needs an audit file in `plan/audit/` (see `plan/RULES.md` Rule 1).
