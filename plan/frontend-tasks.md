# Frontend Task List (vogue-vintage-vibes/)

Legend: `[ ]` todo · `[x]` done (audit file required) · audit links in `plan/audit/`

## Milestone F1 — Wire the store to the Python backend

- [ ] **F1.1 Backend client module** — typed fetch wrapper adding the auth token +
  helpers per endpoint. **Partially done, unlogged:** the file already exists as
  `src/lib/api.ts` (not `src/lib/backend.ts`), reading `VITE_API_URL` and storing the
  JWT under `sande.access_token`. It is **not imported anywhere yet**, so nothing is
  actually wired.
  → audit: [2026-09-19-sole-backend-no-supabase.md](audit/2026-09-19-sole-backend-no-supabase.md)
- [ ] **F1.2 Real coupons in cart** — replace hardcoded `SANDE10` in `src/lib/cart.tsx` + `src/routes/cart.tsx` with `POST /coupons/validate`; keep `discount` out of localStorage
- [ ] **F1.3 Checkout through backend** — `src/routes/checkout.tsx` calls `POST /checkout` (stock-validated, coupon applied) instead of direct Supabase order insert; handle `stock_conflict` issues list in UI
- [ ] **F1.4 Zarinpal flow in payment page** — `src/routes/_authenticated/payment.$orderId.tsx`: call `POST /payments/start`, redirect to gateway, handle `?verify=paid|failed|already_paid&ref=` return, then fall back to the old simulator if backend is unreachable
- [ ] **F1.5 Search bar** — header search opens `GET /search` results (dropdown or `/shop?q=`), wired in `SiteHeader.tsx` + `shop.tsx` query param
- [ ] **F1.6 Live stock in product page & cart** — use `POST /stock/check` on add-to-cart; show "only N left" when stock ≤ 3; disable add when 0
- [ ] **F1.7 Stock decrement shown to admin** — admin products page reflects real stock after backend-decremented orders

## Milestone F2 — Gaps from FEATURES.md part 6 (not started)

> ⚠️ **Blocker before F1.2–F1.7:** the frontend still runs entirely on Supabase
> (24 files import `@/integrations/supabase/*`), while the backend no longer knows
> about Supabase at all. The two data models have diverged — Supabase still has
> `auth.users` + RLS; Postgres/compose now has `public.users` + API-side auth.
> Decide the cut-over strategy (dual-run, or a hard switch behind `api.ts`) before
> wiring pages, and expect auth/session to be the hard part.

- [ ] **F2.1 Contact form persistence** — save via backend (needs backend endpoint) or Supabase table
- [ ] **F2.2 Reviews & ratings** — schema + UI on product page
- [ ] **F2.3 Forgot password** — Supabase reset email flow
- [ ] **F2.4 Admin refund-requests page** — use existing `resolveRefundRequest` server fn
- [ ] **F2.5 Pagination for shop & admin lists**
- [ ] **F2.6 Charts for admin dashboard** — recharts is installed but unused
- [ ] **F2.7 Default address in checkout** — suggest saved addresses; mark `is_default`
- [ ] **F2.8 Shipment tracking number** — admin enters tracking code; shown in order status stepper

## Rules reminder

Every completed F-task needs an audit file in `plan/audit/` (see `plan/RULES.md` Rule 1).
