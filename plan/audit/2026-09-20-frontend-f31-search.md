# Audit — 2026-09-20 — Frontend F3.1 Search (header suggest + history + `?q=` results)

**Task:** `plan/frontend-tasks.md` → Milestone F3 §F3.1 — wire the finished
search backend into the UI: header search box with a debounced
`GET /search/suggest` dropdown (products / categories / tags / recent queries),
search history (recent list, clear-all, per-entry delete), and `shop.tsx`
accepting `?q=` and calling `GET /search` with result count + empty state.

**Pre-flight check (as requested):** all F3 backend endpoints exist
(`backend/app/routers/search.py`, `products.py`, `reviews.py`, `admin.py`) and
the F3.0 API client already had `api.search`, `api.searchSuggest`,
`api.searchHistory`, `api.clearSearchHistory`, `api.deleteSearchHistory`. No
backend work was needed. `DESIGN_SYSTEM.md` was read first and its conventions
were followed (Persian/RTL copy, `@/` imports, `cn()`, brand tokens, Persian
digits via `toFa`, TanStack Query, `sonner` toasts, existing `ui/*` primitives).

## Files changed

| File | Change |
|---|---|
| `vogue-vintage-vibes/src/components/HeaderSearch.tsx` | **New.** Popover search: 250 ms debounced `GET /search/suggest`, images signed through `resolveImageMap`, signed-in recent queries with per-entry delete + clear-all (`useMutation` + query invalidation + toasts), ArrowUp/ArrowDown + Enter keyboard flow, Escape/close resets the field. Suggestions navigate by kind: product → `/product/$id`, known category → `/shop?category=…`, tag/query/raw text → `/shop?q=…`. |
| `vogue-vintage-vibes/src/components/SiteHeader.tsx` | The search icon `Link to="/shop"` was replaced by `<HeaderSearch />`; `Search` icon import moved into the new component. |
| `vogue-vintage-vibes/src/routes/shop.tsx` | `validateSearch` now also parses `?q=` (trimmed, dropped when empty). `ShopPage` dispatches to the new `SearchResults` (server search: count, error, empty and loading states) or the previous `CatalogPage` (unchanged filter/sort behaviour, kept as a separate component so a search never fetches the whole catalog). |
| `vogue-vintage-vibes/src/lib/catalog.ts` | Added `resolveImageMap()` (reference → displayable URL, incl. signed `uploads/…` paths) and `searchQuery(q)` returning `{ query, total, products }` with `GET /search` hits mapped into the local `Product` shape via a new `hitToProduct()`. |
| `vogue-vintage-vibes/src/lib/api.ts` | `SearchHit` / `SearchResult` extracted as exported types and reused by `api.search()` (previously an inline literal). |

## How to verify

Stack: backend on `:8000` + frontend dev server on `:5173` (both were already
running during this task).

1. `cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit -p tsconfig.json` → clean.
2. `./node_modules/.bin/eslint src/components/HeaderSearch.tsx src/components/SiteHeader.tsx src/lib/api.ts src/lib/catalog.ts` → clean.
3. Browser `http://localhost:5173/` → click the header magnifier, type
   `شورت` → dropdown shows «جستجوی …» plus product rows with thumbnails and a
   «محصول» hint; ArrowDown ×2 + Enter, or a click, opens the shop results page.
   `/shop?q=شورت` prints «۸ نتیجه برای «شورت»»; `/shop?q=zzzzqq` prints
   «۰ نتیجه» plus the empty state; `/shop` alone still shows the ۲۰-product
   catalog with the full filter sidebar.
4. Signed in as `customer@sande.local` / `customer1234`: run two searches, reopen
   the header search → «جستجوهای اخیر» lists them newest-first; the per-row ✕
   removes one, «پاک کردن همه» empties the list. Signed out, the dropdown asks
   the visitor to sign in instead of showing history.

Verified here with headless Chrome (DevTools pipe protocol, temporary script,
since deleted): popover opens, suggestions render, ArrowDown+Enter lands on
`/shop?q=شورت` with «۸ نتیجه», history lists `جوراب` + `شورت`, per-entry delete
leaves one, clear-all falls back to the empty copy, and `/shop` keeps its
filters. All temporary files were removed.

## What is NOT done / open

- `plan/frontend-tasks.md` F3.3 (server-side filters/sort, filter chips, compare
  page) is untouched: `?q=` search results intentionally show no sidebar, and
  the catalog filter path still filters client-side over `useCatalog()`.
- `ProductCard` still renders no rating (`avg_rating`/`review_count`) — F3.3.
- `GET /search` does not match tags (the backend searches name, description,
  material, category); a **tag suggestion** therefore submits the tag as a text
  query, so its result list can be empty until the backend searches `tags`.
  Add as new work in the task list.
- Search results are not SSR-prefetched (same as the rest of the catalog), so the
  first paint shows the loading state and hydration fills the grid.
- `shop.tsx` has 4 pre-existing `prettier/prettier` lint errors (lines ~102,
  ~145, ~243, end-of-file) that this change did not touch; intentionally left
  alone to keep the diff minimal. `bun`/`bunx` is not installed in this
  environment and local `node` is v20.9.0, so `vite build` cannot run here
  (`util.styleText` needs Node ≥ 20.12) — typecheck + headless-browser run were
  used instead.
- Documentation: `backend/README.md` and `infra/README.md` were deliberately
  **not** touched (no endpoint, setup or stack change). `vogue-vintage-vibes/README.md`
  was also left alone — it only documents stack/setup, neither of which changed.
