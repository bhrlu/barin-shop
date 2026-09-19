# Audit — F3.0 API client + types

**Date:** 2026-09-20
**Task:** `plan/frontend-tasks.md` **F3.0** — extend the frontend API client and
`Product` type so the catalog backend's new fields and endpoints are usable from
the UI. First step of Milestone F3.

## What was done

All changes are in **`vogue-vintage-vibes/src/lib/api.ts`** (the single data
layer). No UI/route components were touched — this is the typed client surface
the later F3 sub-tasks build on.

1. **Extended the `Product` type** with the fields the backend now returns:
   `tags`, `badge`, `availability`, `available_at`, `low_stock_threshold`,
   `avg_rating`, `review_count`.
2. **Generalized `api.products()`** to `ProductListParams`
   (`category, tag, badge, availability, on_sale, size, color, min_price,
   max_price, sort, include_inactive`) — still backward compatible with the
   existing `api.products({ include_inactive: true })` / `{ category }` callers.
3. **Added catalog methods**: `product` (now URL-encoded), `relatedProducts`,
   `recommendedProducts`, `compareProducts`, `recordProductView`,
   `recentlyViewed`, `productVariants`, `productReviews`, `createReview`,
   `deleteReview`.
4. **Added search methods**: `searchSuggest`, `searchHistory`,
   `clearSearchHistory`, `deleteSearchHistory`.
5. **Added admin methods**: `inventory`, `lowStock`, `adminReviews`,
   `moderateReview`, `replyToReview`, `createVariant`, `updateVariant`,
   `deleteVariant`.
6. **Exported new types**: `Availability`, `ProductBadge`, `ProductSort`,
   `ProductListParams`, `ProductVariant`, `ProductVariantInput`, `Review`,
   `ReviewList`, `ReviewInput`, `SearchSuggestion`, `SearchHistoryEntry`,
   `InventorySummary`, `LowStockProduct`, `LowStockVariant`, `LowStockReport`.

## Files changed

- `vogue-vintage-vibes/src/lib/api.ts`
- `plan/frontend-tasks.md` (F3.0 ticked + audit link)
- `plan/session-log.md` (Session 9)
- `plan/README.md` (audit index)

## How to verify

```bash
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit        # 0 errors
```

Manual sanity (with the stack up): the new methods map 1:1 to endpoints that are
live and smoke-tested — `api.products({ sort: "rating", on_sale: true })`,
`api.searchSuggest("ts")`, `api.productReviews(id)`.

## What is NOT done / open

- **No UI wiring yet** — nothing calls the new methods; that is F3.1–F3.6.
- `src/data/products.ts` (the legacy local `Product` type used by `ProductCard`)
  and `toProduct()` in `src/lib/catalog.ts` were **not** changed. Bridging those
  to the new fields belongs with the UI work (F3.2/F3.3), not F3.0.
- `ProductWrite` (create/update payload) was left as-is; admin editors will add
  `tags/badge/availability/…` in F3.6.
