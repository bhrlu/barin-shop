# Audit — 2026-09-20 — Frontend F3.4 Recently-viewed rail

**Task:** `plan/frontend-tasks.md` → Milestone F3 §F3.4 — «بازدیدهای اخیر» rail on
the home and shop pages, fed by `GET /recently-viewed`.

Pre-flight: the endpoint existed and was smoke-verified since B4.6, and F3.2
already records views with `POST /products/{id}/view` from the product page.
`DESIGN_SYSTEM.md` was read first (Persian/RTL, `@/`, brand tokens, TanStack
Query, `ui/carousel`).

## Files changed

| File | Change |
|---|---|
| `vogue-vintage-vibes/src/components/product/RecentlyViewedRail.tsx` | **New.** Wraps the existing `ProductRail` with `recentlyViewedQuery`: renders only for a signed-in visitor (the endpoint is per-customer) and only when the list is non-empty, so new customers and guests see nothing rather than an empty heading. |
| `vogue-vintage-vibes/src/lib/catalog.ts` | Added `recentlyViewedQuery(limit = 8)` (`["recently-viewed", limit]` → `toProducts()`). |
| `vogue-vintage-vibes/src/routes/index.tsx` | Rail added after the «جدیدترین‌ها» section, inside a `max-w-6xl` wrapper matching the other home sections. |
| `vogue-vintage-vibes/src/routes/shop.tsx` | Rail added at the end of `CatalogPage` (below the grid). |
| `vogue-vintage-vibes/src/routes/product.$id.tsx` | After a successful `recordProductView`, the `["recently-viewed"]` query is invalidated, so the rail is correct even when the visitor leaves the product page before the request settles. |

No backend change was needed.

## How to verify

```bash
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit -p tsconfig.json    # clean
./node_modules/.bin/eslint src/routes/shop.tsx src/routes/product.\$id.tsx \
  src/components/product/RecentlyViewedRail.tsx src/lib/catalog.ts   # clean
```

Browser (stack up) — verified here with headless Chrome over the DevTools pipe
(temporary script, deleted):

| Case | Result |
|---|---|
| signed out, `/` and `/shop` | no «بازدیدهای اخیر» heading at all (the query stays disabled) |
| signed in as `customer@sande.local`, then opening `/product/tshirt-1` and `/product/crop-5` | `/` and `/shop` both show the rail, **newest first**: کراپ‌تاپ بافت ریب آوا (crop-5) → تی‌شرت اورسایز پنبه‌ای مینا (tshirt-1) → the older views this dev customer already had from smoke-test runs (5 slides, embla rail) |

## What is NOT done / open

- **Guests get no rail.** `GET /recently-viewed` requires `CurrentUser`, so a
  signed-out visitor's browsing is not remembered anywhere. A localStorage-based
  guest rail would need a decision on merging it with the account list after
  sign-in (not scheduled).
- The rail has **no remove/clear control** — the endpoint only records and lists
  (no `DELETE /recently-viewed`), so a customer cannot prune their history.
- The **product page** does not show the rail (deliberate: it shows related and
  recommended rails instead).
- `?q=` search results and the compare page also have no rail.
- Guest/empty-state UI is "render nothing" rather than an explanatory block, to
  avoid an empty heading on the home page.
- Docs deliberately untouched: `vogue-vintage-vibes/README.md` (no setup/stack
  change), `backend/README.md` and `infra/README.md` (no backend/infra change),
  `plan/RULES.md`.
