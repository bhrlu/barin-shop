# SÂNDÉ — Full E-commerce Platform Feature Roadmap

English translation of the full feature list. **✅ = already implemented in SÂNDÉ.**
Unchecked items are not yet implemented.

---

## 1. Catalog & Products
- ✅ Product listing with server-side filters (category, size, color, price, tag, badge, availability, on-sale) and sorting (new/popular/rating/price)
- ✅ Live search with autocomplete suggestions and search history (matches name, description, material, category and **tags**)
- ✅ Product variants (size × color) with cross-combination availability and "only N left" alerts on the product page
- ✅ Reviews & star ratings with a rating breakdown, seller replies and a write/edit form
- ✅ Related, recommended and recently-viewed rails, tags/badges display and coming-soon/pre-order states
- ✅ Product comparison (add-to-compare toggle + `/compare` table)
- [x] Product variants (size × color) with separate stock per combination — **backend API done**
- [x] Inventory management with low-stock alerts — **backend API done**
- [x] Customer reviews and star ratings + seller replies — **backend API done**
- [x] Recently viewed and product comparison — **backend API done**
- [x] Related and recommended products — **backend API done**
- [x] Tags, special offers, "coming soon", and pre-order — **backend API done**

> Catalog & Products: live search **UI is done** (F3.1: header suggestions, history,
> `/shop?q=` results); the rest still needs UI wiring. Backend API complete.
> New endpoints: `GET /search/suggest`, `/search/history` (GET/DELETE), product
> `related`/`recommendations`/`compare`/`variants`/`reviews`, `POST /products/{id}/view`,
> `GET /recently-viewed`, variant admin CRUD, `GET /admin/inventory[/low-stock]`,
> `GET /admin/reviews`, `PATCH /reviews/{id}`.
> Product model gained `tags`, `badge`, `availability`, `available_at`,
> `low_stock_threshold`, `avg_rating`, `review_count`.

## 2. Cart & Checkout
- ✅ Persistent cart
- ✅ Saved addresses with a single default — add / edit in place / delete, offered and pre-filled in checkout (F2.7 + F2.7b, B3.10)
- [x] Real discount codes (percent/fixed, usage limits, expiry, minimum purchase) — **backend done (B1.4) + admin manager UI (F4.5)**
- [ ] Guest cart (no sign-up required)
- [ ] Shipping cost by province/weight and tax calculation
- [ ] Stock reservation when placing an order
- [ ] Save cart for later ("next shopping list")

## 3. Payment
- ✅ Gateway page (currently simulated)
- [ ] Real Iranian gateway (Zarinpal, IDPay, Pay.ir, Zibal)
- ✅ Cash on delivery
- [ ] PDF invoice and payment receipt email
- [ ] Installment / credit payment (SnappPay, Torob)

## 4. Shipping & Logistics
- ✅ Shipping steps and status display
- [ ] Multiple carriers with different rates (Post, Tipax, courier)
- [ ] Shipment tracking number and automatic tracking
- [ ] Free shipping above a certain amount
- [ ] Automatic notifications at each step (SMS/email)

## 5. User Account
- ✅ Sign-up/login with email and password (own JWT). **Google sign-in does not exist** in this repo — the claim was a leftover from the Supabase era (corrected 2026-09-22 audit).
- ✅ Profile, orders, addresses (multiple), favorites, payments
- ✅ Order status tracking with sub-steps
- ✅ Cancel order before shipping
- [ ] SMS one-time-password (OTP) login
- [ ] Two-factor authentication
- [ ] Forgot / reset password
- [ ] Wallet and gift credit (Gift Card)

## 6. Marketing & Sales
- [ ] Seasonal and flash sale campaigns (Flash Sale with timer)
- [ ] Email/SMS newsletter
- [ ] Abandoned cart notifications
- [ ] Loyalty program and customer points
- [ ] Banners and campaign landing pages

## 7. Support & Returns
- ✅ Refund request submission, plus the admin settlement centre with the Paya/Satna bank code (B5.3/F2.4)
- ✅ Contact form that stores messages (`POST /contact` + `contact_messages`, F2.1/B3.9) **and the admin inbox screen** (`/admin/messages`, F2.1b — shipped; the "still missing" note was stale, corrected 2026-09-22 audit)
- [ ] Full product return process (step by step)
- [ ] Live chat / support tickets
- [ ] FAQ
- ✅ Size guide

## 8. Admin Panel
- ✅ Dashboard, product management with image gallery, order management, user list
- [x] Pagination on all growing lists (shop, orders, users, payments, messages, reviews) — **envelope API + shared Pager done (F2.5)**
- [x] Daily/monthly sales reports with charts — **KPI endpoint + charts done (B5.2/F2.6)**
- [x] Best-sellers, top customers, and inventory reports — **best-sellers + daily/monthly report endpoint done (B2.2 `/admin/export/report`); top customers & inventory report UI still open**
- [x] Excel/CSV export of orders — **done (B2.2: `/admin/export/orders.{csv,xlsx}` + products exports, StaffOrders guard)**
- [x] Refund request management (approve/reject) — **done (F2.4/B5.3, with bank-tracking settlement)**
- [x] Order detail drawer with fulfilment stepper + printable invoice — **done (F4.4: A4 print, app hidden while printing)**
- [x] Review and discount-code management — **done (admin.reviews + F4.5 coupons manager with toggle/progress/delete)**
- [x] Multiple roles (manager, warehouse, support) — **granular staff roles + per-route enforcement done (B5.4); role-gated admin shell (F4.2); role management UI with two-step confirmation in `/admin/users` (F5.6)**
- [x] Audit-log viewer — **done (F5.5: `/admin/audit` over `GET /admin/audit-logs`, admin/super_admin only; action/entity/staff filters, offset paging, IP + old/new values)**

## 9. Infrastructure & Experience
- [ ] Dark mode
- [ ] PWA (install as mobile app)
- [ ] Blog and SEO content
- [ ] Sitemap and structured data (Product Schema)
- [ ] Multi-language and multi-currency
- [ ] In-app notifications

---

## Todo List (prioritized)

Grouped by effort and whether the backend already supports the feature.
Endpoints noted in `code` already exist and are verified working.

### Catalog & Products — backend API (DONE ✅)
- [x] Extended `GET /products` filters: tag, badge, availability, on_sale, size, color, min/max price, and sort
- [x] Merchandising: `tags`, `badge`, `availability` (in_stock/coming_soon/preorder), `available_at`, `low_stock_threshold`, plus `avg_rating`/`review_count` on every read
- [x] Autocomplete `GET /search/suggest` + history `GET/DELETE /search/history`
- [x] Tag matching in `GET /search` + a tagged starter catalog (tag suggestions now return products)
- [x] Per-variant stock CRUD wired into `POST /stock/check` and checkout (variant stock is authoritative)
- [x] Reviews & ratings with seller replies + admin moderation (`/products/{id}/reviews`, `/admin/reviews`, `PATCH /reviews/{id}`)
- [x] Related / recommended (`/products/{id}/related`, `/recommendations`)
- [x] Recently viewed + comparison (`POST /products/{id}/view`, `GET /recently-viewed`, `GET /products/compare?ids=`) — **UI done** (F3.4 rail, F3.3 compare page)
- [x] Low-stock alerts (`GET /admin/inventory`, `GET /admin/inventory/low-stock`)

### Quick wins — backend already exists, only UI wiring needed
- [x] **Catalog UI wiring** → admin variant editor, admin inventory/low-stock screen, admin review moderation (product page F3.2; shop server-side filters, card ratings, compare view F3.3; recently-viewed rail F3.4; admin screens F3.6)
- [ ] **Admin coupon management screen** → `GET/POST /coupons`, `PATCH /coupons/{id}`, `POST /coupons/generate`
- [ ] **Complete refund UI** → customer request in order detail + admin approve/reject screen → `POST /orders/{id}/refunds`, `PATCH /refunds/{id}`, `GET /admin/refunds`
- [x] **Search box UI** → `GET /search` (F3.1: `HeaderSearch.tsx` + `/shop?q=`, with tag matching since F3.1b)
- [x] **Stock check before checkout** → `api.stockCheck` wired into the cart (F3.5: per-line issues, checkout blocked until the cart validates)
- [x] **Multi-value size/colour filters** → `GET /products` takes repeatable/comma-separated `size`/`color` (B4.12) and the shop chips are multi-select (F3.3c)
- [x] **Enforce availability in the API** → `coming_soon`/`preorder` are rejected by `stock/check` and checkout with reason `not_available` (B4.11); preorder needs an order flag to become orderable (B4.13)
- [ ] **Admin payments list** → `GET /admin/payments`
- [x] **Single-product fetch** → product page uses `GET /products/{id}` (F3.2)
- [x] **Contact form persistence** → `POST /contact` stores the message and `GET/DELETE /admin/contact-messages` reads it (B3.9 + F2.1); the admin inbox screen is F2.1b
- [x] **Default address in checkout** → saved addresses pre-fill the shipping box, `PATCH /addresses/{id}` moves the single default (F2.7 + B3.10)
- [x] **Idempotent payment callback** → `payments.authority` + `already_paid` on a repeat callback/verify (B3.7)

### Core commerce gaps
- [ ] Real Zarinpal gateway (replace simulated flow) → `POST /payments/start`, `POST /payments/verify`, `GET /payments/zarinpal/callback`
- [ ] Reserved inventory on order (variant stock decrement is in; explicit reservation TTL is not)
- [ ] Guest cart + no-signup checkout
- [ ] Shipping rates by province/weight + tax calculation
- [ ] PDF invoice + payment receipt email

### Account & auth
- [ ] Forgot / reset password
- [ ] SMS OTP login
- [ ] Two-factor authentication

### Admin & analytics
- [ ] Sales reports with charts (daily/monthly)
- [ ] Best-sellers / top customers / inventory reports
- [ ] Excel/CSV order export
- [ ] Multiple admin roles (manager, warehouse, support)

### Marketing & engagement
- [ ] Flash-sale campaigns with timer
- [ ] Abandoned-cart notifications
- [ ] Email/SMS newsletter
- [ ] Loyalty points / wallet / gift cards

### Support
- [ ] Full step-by-step return process
- [ ] Support tickets / live chat
- [ ] FAQ page

### Platform / experience
- [ ] Dark mode
- [ ] PWA
- [ ] Blog + SEO content + sitemap + Product Schema
- [ ] Multi-language / multi-currency
- [ ] In-app notifications
