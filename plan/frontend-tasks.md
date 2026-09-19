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
- [ ] **F1.6 Live stock in product page & cart** — use `POST /stock/check` on
  add-to-cart; show "only N left" when stock ≤ 3; disable add when 0
- [ ] **F1.7 Stock decrement shown to admin** — admin products page reflects real stock after backend-decremented orders
- [ ] **F1.9 Lovable preview tooling** — `reportLovableError`/`error-capture` kept
  (no Supabase dependency); revisit once the app runs outside Lovable.

### A1 — open decisions

- **Real Zarinpal redirect** in the payment page (`POST /payments/start` → gateway
  → `?verify=…` return route) instead of the backend's simulated gateway.
- **Google / OAuth login** is gone with Supabase; needs a backend OAuth flow or a
  third-party auth provider before it can return.

## Milestone F2 — Gaps from FEATURES.md part 6 (not started)

> ℹ️ The Supabase-vs-backend blocker that used to sit here is resolved: Session 6
> cut the whole frontend over to the FastAPI backend (see the F1 tracker).

- [ ] **F2.1 Contact form persistence** — save via backend (needs backend endpoint) or Supabase table
- [ ] **F2.2 Reviews & ratings** — schema + UI on product page
- [ ] **F2.3 Forgot password** — Supabase reset email flow
- [ ] **F2.4 Admin refund-requests page** — use existing `resolveRefundRequest` server fn
- [ ] **F2.5 Pagination for shop & admin lists**
- [ ] **F2.6 Charts for admin dashboard** — recharts is installed but unused
- [ ] **F2.7 Default address in checkout** — suggest saved addresses; mark `is_default`
- [ ] **F2.8 Shipment tracking number** — admin enters tracking code; shown in order status stepper

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
- [ ] **F3.2b Availability is UI-only** — `checkout` / `stock/check` ignore
  `coming_soon`/`preorder`, so the API still accepts an order for an unreleased
  product. Backend work → `backend-tasks.md` **B4.11**

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
- [ ] **F3.3c multi-select size/color** — blocked on the backend accepting more
  than one value per param (`backend-tasks.md` **B4.12**)

### F3.4 Recently viewed — DONE

→ audit: [2026-09-20-frontend-f34-recently-viewed.md](audit/2026-09-20-frontend-f34-recently-viewed.md)

- [x] "بازدیدهای اخیر" rail on home/shop (`GET /recently-viewed`) — new
  `components/product/RecentlyViewedRail.tsx` reusing `ProductRail`; renders only
  for signed-in customers with a non-empty list
- [ ] **F3.4b Guest recently-viewed** — the endpoint needs auth, so signed-out
  browsing is not remembered; decide whether a localStorage rail should merge
  with the account list after sign-in (`GET /recently-viewed` has no DELETE either)

### F3.5 Cart (`cart.tsx`)

- [ ] Wire `POST /stock/check` on add-to-cart / cart open; surface per-line issues
  and per-variant availability

### F3.6 Admin

- [ ] Product editor (`admin.products.tsx`): fields for `tags`, `badge`,
  `availability`, `available_at`, `low_stock_threshold`
- [ ] Variants editor per product (create / patch stock / delete)
- [ ] Inventory / low-stock screen (`GET /admin/inventory`,
  `/admin/inventory/low-stock`)
- [ ] Reviews moderation screen: hide/publish + seller reply (`GET /admin/reviews`,
  `PATCH /reviews/{id}`)

### F3.7 Supersedes open F1/F2 items

- [x] F1.5 search bar → covered by F3.1
  → audit: same file as F3.1
- [ ] F1.6 live stock in product page & cart → covered by F3.2/F3.5
- [ ] F2.2 reviews & ratings → schema + API now exist; UI is F3.2

## Rules reminder

Every completed F-task needs an audit file in `plan/audit/` (see `plan/RULES.md` Rule 1).
