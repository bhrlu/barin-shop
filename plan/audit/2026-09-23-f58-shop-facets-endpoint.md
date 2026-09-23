# Audit — F5.8 Remove duplicate `/shop` catalog fetch (2026-09-23)

## Task

`F5.8` (P2, Batch D). Every `/shop` visit ran two requests:

- `catalogQuery`: `GET /products?include_inactive=true`, every product, plus
  `POST /storage/sign` for every stored image;
- the paginated, server-filtered list query.

The full catalogue was used only to build the filter options: sizes, colours, tags
and the price-slider bounds. Acceptance: normal, filtered and search visits must not
issue unnecessary full-catalogue requests. Part of the "continue the whole backlog"
run; follows F5.12, which removed the same fetch from `CartProvider`.

## Spec check (Rule 0)

The spec has no `/shop` section. Its filtering rule for data tables (`B3`,
"server-side pagination/sorting/filtering") points the same way: the server owns the
filter data. `B1` (no visual change, Persian copy) holds, and the filter panel looks
identical. The stack header (Supabase / `createServerFn`) is ignored: the new endpoint
is FastAPI and the client goes through `src/lib/api.ts`.

## Recon / contract (Rules 6–9)

- **Data flow:** `routes/shop.tsx` → `useCatalog()` (`src/lib/catalog.ts`) →
  `api.products({include_inactive: true})` → `routers/products.py::list_products`.
  The facet derivation (`allSizes`, `allColors`, `priceBounds`) lived in `useCatalog`
  and had exactly one consumer, `/shop`. `src/data/products.ts` has same-named
  exports, but that is the old static mock and is not imported for this.
- **Alternatives considered:**
  - Frontend-only (e.g. drop image signing): still downloads every product on each
    visit.
  - Derive facets from the 12-item page: wrong, because the filter options must
    cover the whole catalogue.

  Only a server-side aggregate removes the full-catalogue request.
- **New contract:** `GET /products/facets`
  - Public, no auth dependency, always 200.
  - Response:
    `{sizes: string[], colors: {name, hex}[], tags: string[], price_min: int|null, price_max: int|null}`.
  - Content: **active products only, whoever asks.**
  - Ordering: first-seen over the newest-first list (`created_at DESC, id`); colours
    are deduped by name, first position with the last hex, like the JS `Map` it
    replaces.
  - `null` bounds when nothing is active. The client keeps its old `0 / 2 000 000`
    fallback.
  - Declared before `/products/{product_id}` so the path is not shadowed.
- **Security:** read-only. The endpoint exposes only values already public through
  `GET /products` for anonymous callers. Inactive products never contribute, so staff
  viewers no longer see tags that exist only on inactive products. Before, `/shop`
  built tags from `all`, which includes inactive rows for catalogue staff. The shopper
  view is unchanged.
- **Money/stock:** untouched. The price range is display-only; filtering stays in
  `GET /products`.

## What was done

- **Backend:**
  - `ProductFacets` schema;
  - `GET /products/facets` in `routers/products.py`, one query over four columns of
    the active products.
- **Frontend:**
  - `ProductFacets` type and `api.productFacets()` in `src/lib/api.ts`;
  - `facetsQuery` in `src/lib/catalog.ts`. Its key is `["catalog", "facets"]`, so the
    existing admin `invalidateQueries({queryKey: ["catalog"]})` calls refresh it by
    prefix. Tags are still sorted with `localeCompare(…, "fa")`.
  - `CatalogPage` (`/shop`) reads its filter options from `facetsQuery` and no longer
    calls `useCatalog()`. The product grid's skeleton now waits only for the product
    query (before, it also waited for the catalogue).
  - The now-unused facet fields were removed from `useCatalog()` (R7: one
    derivation, now on the server).
- `/shop?q=` (search) was already search-only once F5.12 landed. It is verified here.

## Files changed

- `backend/app/routers/products.py`, `backend/app/schemas.py`
- `backend/tests/test_product_facets.py` (new, 5 tests), `backend/tests/api_smoke.py`
  (+1 check)
- `vogue-vintage-vibes/src/lib/api.ts`, `src/lib/catalog.ts`, `src/routes/shop.tsx`
- docs:
  - `backend/README.md` (endpoint row);
  - `vogue-vintage-vibes/FEATURES.md` (row ۱.۲);
  - this audit;
  - `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/session-log.md`,
    `plan/README.md`.

## How to verify

**Backend:** `pytest tests/test_product_facets.py` — 5 passed, stable over 5 runs
including one during a backend hot reload. The tests:

- **Equality with the old derivation:** facets equal the values derived from the
  anonymous `GET /products`.
- **Inactive products:** they never contribute, for a guest or for an admin.
- **Ordering:** first-seen order and colour dedupe.
- **Price floor:** the cheapest active product sets `price_min`.
- **Empty catalogue:** no active product → empty lists and `null` bounds (checked in
  the same, uncommitted transaction).

Mutation controls:

- Without the `active` filter, 2 tests fail.
- With the route unregistered, 4 fail.

(One chained run stacked both mutations and failed 5 tests; that run is discarded.)

Full gates:

- `pytest -q` 208 passed;
- `ruff check app tests` clean;
- `tests/api_smoke.py` 231/0, including the new facets check against the bare list.

**Browser** (Playwright, guest and admin): 23 checks, 0 failed.

- **`/shop`:**
  - 0 full-catalogue requests, exactly 1 facets and 1 page request;
  - the filter panel lists every size, colour and tag from the facets;
  - the price slider's `aria-valuemin`/`max` equal `price_min`/`price_max`;
  - the grid and total match the API.
- **Size chip (SPA):** only the page query refetches (no catalogue, no facets), and
  the count matches the API.
- **Filtered full load** (`?category=tshirt&size=…`): no catalogue request, and the
  filters reach the API.
- **Pager to page 2:** no catalogue or facets request.
- **`/shop?q=تی`:** only `/search`.
- No page errors.

**Negative control:** the same script against `HEAD`'s `api.ts`, `catalog.ts` and
`shop.tsx`. **6 checks fail**: the catalogue request and the missing facets request,
on the normal and filtered visits, for guest and admin. The other 17 pass on both. So
the filter options the page shows, and the slider bounds, are the same as the old
client-side derivation.

**Frontend gates:**

- `prettier --check` (changed files) clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / 16 warnings (unchanged since F5.12);
- `bun run build` OK.

No DDL, infra or seed change (the endpoint reads existing columns), so a clean
environment is not required (R14).

**Verification level:** browser tested + integration tested (backend).

## What is NOT done / open

- The endpoint returns every active value, not counts per facet or options narrowed
  by the other active filters. The old page did not have that either.
- Sizes keep the old first-seen order, not a canonical XS→XL order. That was existing
  behaviour and is out of scope.
- `infra/README.md`, `DESIGN_SYSTEM.md`, `feature-roadmap.md`: untouched. There is no
  setup, token or roadmap-level change.
