# Audit — 2026-09-22 — Pagination everywhere (F2.5)

## Task

"Check all APIs; where a list can grow, add pagination and update the UI"
(= F2.5 «صفحه‌بندی لیست‌ها» in `plan/frontend-tasks.md`).

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` before starting. It does not prescribe a
pagination scheme; the envelope (`{items,total,page,page_size,pages}`) and
page-size caps follow repo conventions. B0/B1 rules followed in the new
`Pager` (Persian digits, terracotta active page, token classes, RTL chevrons).
No Rule-4 status strings or cart money rules touched.

## What was done

### Backend — envelope pagination, backward-compatible

- **New `app/services/pagination.py`** — `Page envelope` builder:
  `paginate(total, page, page_size, rows)` plus `PageParams` dependency
  (`page` ≥ 1, `page_size` 1–100, default 20). **No `page` param → the
  endpoint keeps returning a bare list**, so existing callers (mobile,
  smoke, tests) never break.
- Paginated (`?page=&page_size=` → envelope):
  - `GET /products` (public catalog; combined count inside the dynamic WHERE)
  - `GET /orders` (customer; count via `COUNT(*) OVER()` with the GROUP BY)
  - `GET /admin/orders`, `/admin/users`, `/admin/payments`,
    `/admin/contact-messages`, `/admin/reviews`
- `GET /admin/audit-logs` gained `offset` (limit/offset paging is the right
  model for an append-only log the UI scrolls newest-first).
- **Bug found & fixed en route:** `routers/products.py::_optional_admin`
  passed `resolve_role()` (a **string**) as `AuthUser.roles` — after B5.4's
  set-based roles any *authenticated* call to `/products` crashed with
  `TypeError: 'str' & set`. Now uses `resolve_roles()` (set). This was a live
  500 on every logged-in product list, caught by the smoke's own traffic.
- Latent single-use B6.1 leftover in `products.py` (unused import style) not
  present; ruff clean.

### Frontend — shared Pager + paged screens

- **New `components/Pager.tsx`** — numbered pager with ellipsis window,
  Persian digits, terracotta active page, RTL chevrons (prev = right),
  total count, hidden when `pages ≤ 1`, `aria-current` on the active page.
- `api.ts`: `Page<T>` type, `toPage()` normalizer (overloaded for arrays and
  promises), and page params on `products`, `orders`, `adminOrders`,
  `adminUsers`, `adminPayments`, `adminContactMessages`, `adminReviews`.
- Paged screens (state lives in the component or the URL):
  - `/shop` — `page` is a URL search param (validateSearch), 12 per page,
    count line shows the envelope total, Pager resets cleanly with filters
  - `/admin/orders`, `/admin/users`, `/admin/messages`, `/admin/reviews` —
    20 per page, `setPage` state, Pager under the list
  - `/account/orders` — 10 per page
- Deliberately **not** paged: refunds (small), coupons (small), inventory
  report (bounded by catalog), favorites/search rails (already limited).
- `adminPayments` gained page params but there is no admin payments screen
  (client was unused); left as API-only capability.

## Files changed

- `backend/app/services/pagination.py` (new)
- `backend/app/routers/products.py` (pagination + roles fix)
- `backend/app/routers/orders.py` (customer list pagination)
- `backend/app/routers/admin.py` (5 list endpoints + audit offset)
- `backend/app/routers/contact.py`, `backend/app/routers/reviews.py`
  (admin list pagination)
- `backend/tests/api_smoke.py` (F2.5 section: 8 endpoints asserted)
- `vogue-vintage-vibes/src/lib/api.ts` (Page/toPage + client params)
- `vogue-vintage-vibes/src/lib/catalog.ts` (bare-array cast note)
- `vogue-vintage-vibes/src/components/Pager.tsx` (new)
- `vogue-vintage-vibes/src/routes/shop.tsx` (URL-param paging)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.{orders,users,messages,reviews}.tsx`
- `vogue-vintage-vibes/src/routes/_authenticated/account.orders.tsx`

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests             # clean
./.venv/bin/python tests/api_smoke.py                  # 170 checks, 0 failed
cd vogue-vintage-vibes
PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$HOME/.bun/bin:$PATH" \
  bunx tsc --noEmit && bun run build                   # clean / passes
```

Live spot-checks (all envelopes carry correct totals/pages):
`/products?page=2&page_size=6` → 20/4 · `/admin/orders?page=2` → 65/10 ·
`/admin/users` → 81/9 · `/admin/payments` → 80/14. UI: shop pager shows 4
pages and flips via `?page=`; admin lists show «۱ … ۱۰» windows.

## What is NOT done / open

- **Infinite-scroll** alternative for the shop was not requested; Pager is
  the single convention. Revisit if the catalog grows past ~50 items/page.
- `adminPayments` has no screen (pre-existing gap, separate task).
- `GET /admin/audit-logs` UI (BE-04 surface) still limit/offset only —
  acceptable for an ops table; a Pager is trivial to add if a screen ships.
- `include_inactive` + paging on `/products` was verified manually
  (admin 20/1) but not smoke-asserted; low risk.
- Docs touched: this audit, task ticks (F2.5), session log 29, plan README,
  backend README (pagination contract), FEATURES ۳.۱, roadmap.
