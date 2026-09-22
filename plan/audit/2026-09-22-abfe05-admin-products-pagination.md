# AB-FE-05 — Admin products server pagination

**Date:** 2026-09-22 · **Task:** `AB-FE-05` (P1, Batch B, `plan/MASTER-BACKLOG.md`;
from `[FE-04]`, completes F2.5; full-backlog audit §AB-FE-05) · **Layer:** frontend
only

## Task

`/admin/products` rendered the whole catalogue from `useCatalog()`, the shared
`["catalog"]` query that loads every product with `include_inactive=true`. It was
the last growing admin list without F2.5 paging. AB-FE-05 moves it onto the
paginated `GET /products` envelope and adds:

* URL-driven `?page=` plus filters that survive paging and reset it;
* the server total and page count;
* loading, error and empty states;
* invalidation on every admin mutation.

## Spec check (Rule 0)

Followed:

* **[FE-04]** — the product manager lists the catalogue with category and
  availability state visible; server-side pagination per **[FE-02]**'s "server-side
  pagination/filtering".
* **B0.4 / B0.5 / B4.3** — pulse skeleton on the first load instead of the old
  «در حال بارگذاری…» text; `rounded-xl` filter selects; dashed empty state; the
  error panel uses the `destructive` tokens (DESIGN_SYSTEM §2.3).
* **B1.4 / B1.6** — Persian copy and digits (the shared `Pager`), 375 px checked.
* **[FE-01].3** — support direct URL entry still gets the Persian role notice, and no
  product request is made.

Deliberately not followed:

* **[FE-02] `AdminDataTable`** (search box, sort headers, bulk bar) — that is F4.3.
  The shared `Pager` is used, as in every other F2.5 list.
* **Text search on this page** — `GET /products` has no `q` parameter (search is the
  separate `/search` endpoint, which returns reduced `SearchHit` rows and
  storefront-only products). The backlog says "preserve filters/search" where they
  exist. The page had no search before, and inventing a backend search parameter
  was out of scope, so the page offers the server-supported **category** and
  **availability** filters instead.
* **Spec stack wording** — stale (FastAPI + `api.ts`).

## Architecture check (Rules 6–9)

* **Owning module:** `src/routes/_authenticated/admin.products.tsx`;
  `src/components/admin/VariantEditor.tsx` (one invalidation line).
* **Data flow:** route search → `useQuery(["admin-products", filters, page])` →
  `api.products({category, availability, include_inactive: true, page,
  page_size: 20})` → `toPage()` → `toProducts()` (image signing, same mapper as
  before) → `GET /products`.
* **Contract (unchanged, verified live):**
  * `GET /products?page=&page_size=` (≤100) returns the F2.5 envelope `{items,
    total, page, page_size, pages}`; without `page` it returns a bare array.
  * Filters: `category`, `availability` and others; default sort `new` =
    `created_at DESC`, the same order the old bare list used.
  * `include_inactive=true` is honoured only when `user.is_admin`.
  * The query is public (no auth needed); the admin shell gates the page.
* **Why a separate query key:** `["catalog"]` is shared with the storefront (cart
  provider, checkout, favorites, home, shop facets, admin reviews' `byId`). It stays
  untouched. The admin list gets `["admin-products", …]`.
* **Invalidation (the Rule 6 consumer list):**
  * product save/delete → `["admin-products"]` + `["catalog"]`;
  * `VariantEditor` → adds `["admin-products"]` next to its existing `["catalog"]`,
    inventory and low-stock keys;
  * `admin.reviews.tsx` and the storefront `ReviewsSection` still invalidate
    `["catalog"]` only. The admin list doesn't display ratings, so it needs no
    refresh from them.
* **URL state:** `validateSearch` on the route (`page`, `category`,
  `availability`), in the same style as `shop.tsx`.
* **Router bug found and fixed:** TanStack Router merges a child route's validated
  search **over the parent's raw search**, and the root has no validator. So a
  key that `validateSearch` simply omits is inherited raw: `?page=abc` reached the
  API (422) and `?category=hack` produced an empty list. Invalid keys are now
  returned as explicit `undefined`, and the URL is canonicalised
  (`/admin/products?page=abc&category=hack` → `/admin/products`).
  `/shop?page=abc` has the same pre-existing leak (3 retried 422s, no products) —
  recorded as `F5.11`, not touched here.
* **Out-of-range pages:** a delete, or a stale link, can point past the last page.
  Once real (non-placeholder) data says so, the page `replace`-navigates to the
  last page. The guard waits for `isSuccess && !isPlaceholderData`. An earlier
  draft of mine checked only `!isPlaceholderData`, which would have bounced a cold
  load of `?page=3` to page 1 while `pages` was still unknown. That was caught
  in review and is covered by a refresh-on-`?page=3` check.
* **Security (R9):** read-only list. The backend decides `include_inactive`. The
  page is reachable only by roles with the `products` tab (admin, super_admin,
  order_manager).
* **Blast radius:** only this route and VariantEditor changed. `useCatalog()` and
  `catalogQuery` are unchanged for all their other consumers. The AB-FE-02 export
  buttons on this page re-ran green (45/45).

## What was done

1. `admin.products.tsx`:
   * `validateSearch` with explicit-`undefined` normalisation, and `cleanSearch()`
     for navigation;
   * paginated query (20 per page) with `placeholderData: keepPreviousData`, so a
     page change keeps the old rows dimmed (`opacity-60`, `aria-busy`) instead of
     blanking;
   * heading count from the server `total`;
   * «دسته» and «وضعیت عرضه» selects plus «حذف فیلترها»; any filter change drops
     `page`;
   * skeleton, error panel with «تلاش دوباره», and an empty state that
     distinguishes filtered from truly empty;
   * shared `Pager` driving `?page=`;
   * out-of-range guard;
   * mutations invalidate both keys.
2. `VariantEditor.tsx` — also invalidates `["admin-products"]`.

## Files changed

* `vogue-vintage-vibes/src/routes/_authenticated/admin.products.tsx`
* `vogue-vintage-vibes/src/components/admin/VariantEditor.tsx`
* `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/backend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`, `plan/feature-roadmap.md`
* `vogue-vintage-vibes/FEATURES.md`, `vogue-vintage-vibes/DESIGN_SYSTEM.md`
* this audit

## Tests / verification (all executed in this session)

| Check | Result |
| --- | --- |
| `bunx tsc --noEmit` | clean |
| `bun run lint` | 0 errors, 15 pre-existing warnings (none in touched files) |
| `prettier --check` on touched files | clean |
| `bun run build` | OK |
| backend `pytest -q` against the live DB | 72 passed (backend untouched) |
| `ruff check app tests` | clean |
| `tests/api_smoke.py` | 196 checks, 0 failed |
| Headless Chromium script with 25 fixture products | **36 checks, 0 failed** (run twice) |
| F5.5 / F5.6 / AB-FE-02 browser suites (regression) | 35/35, 40/40, 45/45 |

**Fixtures.** The dev catalogue has 20 products, which is a single page, so the
script first created 25 throwaway products through the admin API (`F-AB05 آزمون
01…25`, category `set`, #1–5 inactive, #6–10 `coming_soon`), for 45 total and 3
pages. It deleted them in a `finally` block and asserted that the catalogue was
back to 20.

**Checks.**

* **Guard:** support → role notice, zero paginated product requests.
* **Paging:**
  * page 1 is requested as `?include_inactive=true&page=1&page_size=20` and shows
    20 rows, the heading `(۴۵)` and the pager `۴۵ مورد`;
  * page 2 → URL `?page=2`, request `page=2`, different rows, including the 5
    inactive fixtures marked «غیرفعال»;
  * page 3 → the 5-row remainder;
  * a refresh on `?page=3` stays on page 3.
* **Filters:**
  * category `set` → URL `?category=set` (page dropped), request `category=set&page=1`,
    20 rows all «ست»;
  * paging keeps the filter (URL and request), and page 2 has 29 − 20 = 9 rows;
  * changing availability on page 2 resets to page 1 → 5 «به‌زودی» rows, pager
    hidden;
  * `socks` + `coming_soon` → the filtered empty state;
  * «حذف فیلترها» → clean URL, full list.
* **URL hygiene:**
  * junk params are dropped from the request and the URL;
  * `?page=9` is replaced by `?page=3`;
  * direct entry `?category=set&page=2` shows the selected filter and 9 rows.
* **Mutations:**
  * a UI delete removes the row and the total drops by 1;
  * a UI edit of the price shows «۷۷۷,۰۰۰» on the row;
  * adding a variant triggers a refetch of the paginated list.
* **Loading and error:**
  * with a 1.5 s delayed page 2, the old 20 rows stay visible with
    `aria-busy="true"`;
  * a cold load shows the 5-bar skeleton;
  * a mocked 500 shows the error panel, and retry recovers to 20 rows.
* **Other:**
  * no page errors;
  * `/shop` still renders its cards, and the storefront API never returns the
    inactive fixtures;
  * 375 px → no horizontal scroll.

**Whole-table loading, measured honestly.** The products page no longer depends on
the bare catalogue, but one bare `GET /products?include_inactive=true` still fires
on `/admin/products`. It fires the same way on `/admin/orders` (1 vs 1): it comes
from `CartProvider` in `__root.tsx`, which loads `catalogQuery` on every route.
Recorded as `F5.12`.

**Evidence for `B5.4b`.** As order_manager, the same list reports 39 = 44 − 5, so the
inactive products are hidden from a role that is allowed to edit the catalogue.

During development: the first run had 4 timing failures (assertions read
placeholder rows) and one crash in a delayed route handler. The script now waits
for the paginated response and for `aria-busy` to clear, and both runs since were
36/36. A test assertion that had been written hollow (`|| true`) was replaced by a
real one (the 5 inactive rows on page 2) before the passing runs.

## Verification level

**browser tested** (+ type/lint/build and backend regression suites). No infra/
DB/seed/config change, so Rule 14 does not apply.

## What is NOT done / open

* **New `B5.4b` (discovered as `NEW-ABFE05-1`, P2, backend):** `GET /products`
  honours `include_inactive` only for `is_admin` (admin/super_admin), not for the
  `catalog` capability. So an `order_manager`, who may edit products, never sees
  inactive products in this list and cannot re-activate them from the UI.
* **New `F5.11` (discovered as `NEW-ABFE05-2`, P3, frontend):** `/shop`'s
  `validateSearch` omits invalid keys instead of returning `undefined`, so
  `?page=abc` / `?category=hack` leak through the router merge to the API
  (`/shop?page=abc` → 422 ×3, no products).
* **New `F5.12` (discovered as `NEW-ABFE05-3`, P2, frontend):** `CartProvider` in
  `__root.tsx` runs `catalogQuery` (the whole catalogue, `include_inactive=true`)
  on every route, admin pages included. It is related to `F5.8` (`/shop` fetches
  the catalogue twice) but broader.
* No text search on the admin list (the contract has none).
* Filters: category and availability only. Badge, tag, price and sort are
  supported by the API but were not requested.
* A product saved while on page 3 appears on page 1 (`created_at DESC`); there is no
  auto-jump to it.
* Delete still has no confirmation dialog (pre-existing; not in this task).
* Not touched: F4.3, F5.8, the storefront `useCatalog()` consumers.
* Docs untouched on purpose: `backend/README.md` (no endpoint change),
  `infra/README.md`, `vogue-vintage-vibes/README.md`, the spec.
