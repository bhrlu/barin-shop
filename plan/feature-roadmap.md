# SÂNDÉ — Full E-commerce Platform Feature Roadmap

English translation of the full feature list. **✅ = already implemented in SÂNDÉ.**
Unchecked items are not yet implemented.

---

## 1. Catalog & Products
- ✅ Product listing with filters (category, size, color, price) and sorting
- [x] Live search with autocomplete suggestions and search history — **backend API done**
- [x] Product variants (size × color) with separate stock per combination — **backend API done**
- [x] Inventory management with low-stock alerts — **backend API done**
- [x] Customer reviews and star ratings + seller replies — **backend API done**
- [x] Recently viewed and product comparison — **backend API done**
- [x] Related and recommended products — **backend API done**
- [x] Tags, special offers, "coming soon", and pre-order — **backend API done**

> Catalog & Products: backend API complete (UI wiring still pending for most of these).
> New endpoints: `GET /search/suggest`, `/search/history` (GET/DELETE), product
> `related`/`recommendations`/`compare`/`variants`/`reviews`, `POST /products/{id}/view`,
> `GET /recently-viewed`, variant admin CRUD, `GET /admin/inventory[/low-stock]`,
> `GET /admin/reviews`, `PATCH /reviews/{id}`.
> Product model gained `tags`, `badge`, `availability`, `available_at`,
> `low_stock_threshold`, `avg_rating`, `review_count`.

## 2. Cart & Checkout
- ✅ Persistent cart
- [ ] Guest cart (no sign-up required)
- [ ] Real discount codes (percent/fixed, usage limits, expiry, minimum purchase)
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
- ✅ Sign-up/login with email and Google
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
- ✅ Refund request submission (infrastructure ready, UI half-done)
- [ ] Full product return process (step by step)
- [ ] Live chat / support tickets
- [ ] FAQ
- ✅ Size guide

## 8. Admin Panel
- ✅ Dashboard, product management with image gallery, order management, user list
- [ ] Daily/monthly sales reports with charts
- [ ] Best-sellers, top customers, and inventory reports
- [ ] Excel/CSV export of orders
- [ ] Refund request management (approve/reject)
- [ ] Review and discount-code management
- [ ] Multiple roles (manager, warehouse, support)

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
- [x] Per-variant stock CRUD wired into `POST /stock/check` and checkout (variant stock is authoritative)
- [x] Reviews & ratings with seller replies + admin moderation (`/products/{id}/reviews`, `/admin/reviews`, `PATCH /reviews/{id}`)
- [x] Related / recommended (`/products/{id}/related`, `/recommendations`)
- [x] Recently viewed + comparison (`POST /products/{id}/view`, `GET /recently-viewed`, `GET /products/compare?ids=`)
- [x] Low-stock alerts (`GET /admin/inventory`, `GET /admin/inventory/low-stock`)

### Quick wins — backend already exists, only UI wiring needed
- [ ] **Catalog UI wiring** → search box + suggestions + history, reviews/ratings UI, related/recommended carousels, compare view, recently-viewed rail, availability/badge/tags filters, variant picker + admin variant editor, admin inventory/low-stock screen
- [ ] **Admin coupon management screen** → `GET/POST /coupons`, `PATCH /coupons/{id}`, `POST /coupons/generate`
- [ ] **Complete refund UI** → customer request in order detail + admin approve/reject screen → `POST /orders/{id}/refunds`, `PATCH /refunds/{id}`, `GET /admin/refunds`
- [ ] **Search box UI** → `GET /search`
- [ ] **Stock check before checkout** → wire `api.stockCheck` into the cart
- [ ] **Admin payments list** → `GET /admin/payments`
- [ ] **Single-product fetch** → use `GET /products/{id}` on the product page

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
