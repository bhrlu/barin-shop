# Audit — Bridge legacy `Product` type + `toProduct()` to catalog fields

**Date:** 2026-09-20
**Task:** Follow-up to **F3.0** — make the catalog fields introduced in the API
client reachable from the UI. The legacy `@/data/products` `Product` type (used
by `ProductCard`, shop, product page) and `toProduct()` in `@/lib/catalog` were
not carrying the new backend fields.

## What was done

1. **`src/data/products.ts`** — extended the `Product` type with the catalog
   fields, **optional** so the static seed data below it still type-checks:
   `tags?`, `badge?` (`ProductBadge | null`), `availability?` (`Availability`),
   `availableAt?`, `lowStockThreshold?`, `avgRating?`, `reviewCount?`. Reuses the
   `Availability` / `ProductBadge` unions from `@/lib/api` (single source of
   truth).
2. **`src/lib/catalog.ts`** — `AdminProduct` now declares those fields as
   **required** in its intersection, and `toProduct()` populates them from the
   API row (`tags`, `badge`, `availability`, `available_at`,
   `low_stock_threshold`, `avg_rating`, `review_count`). `useCatalog()` therefore
   exposes them to every consumer (`shop`, product page, admin).

No data or UI behavior changed — this is purely the type/mapping bridge. The
static seed array and the dead `allSizes`/`allColors`/`priceBounds`/`getProduct`
exports in `data/products.ts` were left untouched (they are unused now).

## Files changed

- `vogue-vintage-vibes/src/data/products.ts`
- `vogue-vintage-vibes/src/lib/catalog.ts`
- `plan/frontend-tasks.md` (F3.0 bridge bullet)
- `plan/session-log.md` (Session 9 addendum)
- `plan/README.md` (audit index)

## How to verify

```bash
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit        # 0 errors
```

After this, `const { products } = useCatalog()` yields items with `tags`,
`badge`, `availability`, `avgRating` and `reviewCount` available for the F3.2 /
F3.3 UI.

## What is NOT done / open

- Nothing consumes the new fields yet — the shop filters/ratings, product-page
  badges, variant picker and reviews UI are still F3.1–F3.6.
- The unused static seed exports in `data/products.ts` are dead code; removing
  them is a separate cleanup (not done here to keep the diff scoped).
