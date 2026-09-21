# Audit — B4.11 availability enforcement + B4.12 multi-value facets (+ F3.3c) — 2026-09-21

**Task (user request):** implement **B4.11** (enforce `availability` in
`/stock/check` and checkout) and **B4.12** (multi-value `size`/`color` filters),
"so availability is enforced in the API and multi-select size/color filters
work". The user chose:

- **Block both `coming_soon` and `preorder`** (one reason, no per-state code).
- **Include the shop's multi-select chips** (F3.3c) so the capability is usable
  end to end, not just an API option.

---

## What was done

### B4.11 — `availability` is a hard gate

1. **New `app/services/availability.py`** with `availability_issue(product)`:
   returns `"not_available"` for anything that is not `in_stock` (a missing/null
   column falls back to orderable, so pre-migration rows cannot start failing).
   Both endpoints call the same helper — the pre-check and the order can never
   disagree.
2. **`POST /stock/check`** (`routers/stock.py`) now selects `availability` and
   reports `not_available` **before** the size/variant/stock checks, so a
   `coming_soon` product is rejected for that reason rather than a misleading
   stock or size one.
3. **Checkout** (`services/checkout.py`) selects `availability` inside the same
   `FOR UPDATE` lock and raises the same issue, so a direct API call cannot order
   an unreleased product. The HTTP shape is unchanged: **409** with
   `code: "stock_conflict"` and `issues: [{product_id, reason: "not_available",
   available: 0}]` — no new status string, no change to order/payment statuses.
4. **Preorder stays unorderable** (the user's choice): there is no preorder flag on
   `orders`, so letting it through would silently promise a delivery the model
   cannot express. Enabling it later = relax `availability_issue()` + add the flag;
   documented in the new module's docstring and in `backend/README.md`.
5. **`StockIssue.reason` is now a documented closed set** in `app/schemas.py`
   (`not_found`, `inactive`, `not_available`, `size_invalid`,
   `insufficient_stock`) with a per-reason comment. `size_invalid` was **already**
   emitted by checkout but missing from the schema and from the frontend type —
   now declared everywhere, and `/stock/check` uses it for a size the product does
   not offer instead of mislabelling that as `insufficient_stock`.

### B4.12 — multi-value `size` / `color`

6. **New `app/services/catalog_filters.py`** with `split_multi()`: flattens
   repeated params and comma-separated values, trims, drops empties, dedupes
   (order kept). Both shapes now work: `?size=M&size=L`, `?size=M,L`, even
   `?size=M&size=L,M`.
7. **`GET /products`** takes `size` and `color` as `list[str] | None` and applies
   **OR within a facet, AND across facets**. When both facets are present the match
   is resolved **per combination** — at least one requested size × colour pair must
   still be purchasable, so a pair the admin deactivated with a variant row is not
   advertised as offered. A missing variant row still falls back to aggregate stock
   (the backend's own rule), so widening either facet keeps the product.

### F3.3c — the shop sidebar is multi-select

8. **`shop.tsx`**: `size`/`color` are `string[]` in the route search; `?size=M&size=L`
   parses to `["M","L"]`, chips toggle instead of replace (`aria-pressed`, headings
   marked «چند انتخابی»), and `clean()` also drops empty arrays so a link never
   carries `?size=`.
9. **`api.ts`**: `ProductListParams.size/color` accept `string | string[]` and are
   sent as **repeated** params (`qs.append`), the shape verified against the
   backend; `StockIssue.reason` uses the new `StockIssueReason` union.
10. **New `src/lib/stock-issues.ts`**: one copy of the Persian message per reason,
    shared by the cart line notes (`stockIssueMessage`, which uses the product's own
    `availability` to say «پیشفروش» vs «هنوز عرضه نشده», since the API reports a
    single reason) and the checkout toast (`stockIssueLabel`). The checkout toast
    for a rejection is no longer «موجودی کافی نیست» for something that is not a
    stock problem.

---

## Files changed

| File | Change |
|---|---|
| `backend/app/services/availability.py` | **new** — `availability_issue()`, the shared gate |
| `backend/app/services/catalog_filters.py` | **new** — `split_multi()` for repeatable/comma facets |
| `backend/app/routers/stock.py` | `availability` column + `not_available` gate; `size_invalid` for a missing size |
| `backend/app/services/checkout.py` | same gate inside the locked transaction |
| `backend/app/routers/products.py` | multi-value `size`/`color` + per-combination semantics |
| `backend/app/schemas.py` | `StockIssue.reason` documented closed set (+ `not_available`, `size_invalid`) |
| `backend/tests/test_availability_and_filters.py` | **new** — 14 unit tests (gate + parser) |
| `backend/tests/api_smoke.py` | multi-value facet assertions + a live availability-guard round trip |
| `backend/README.md` | availability gate + facet semantics documented |
| `vogue-vintage-vibes/src/lib/stock-issues.ts` | **new** — shared Persian issue copy |
| `vogue-vintage-vibes/src/lib/api.ts` | repeatable `size`/`color` params; `StockIssueReason` |
| `vogue-vintage-vibes/src/routes/shop.tsx` | multi-select size/colour chips + array URL |
| `vogue-vintage-vibes/src/routes/cart.tsx` | uses `@/lib/stock-issues` |
| `vogue-vintage-vibes/src/routes/checkout.tsx` | reason-aware rejection toast |

Docs updated in the same session: `plan/backend-tasks.md`,
`plan/frontend-tasks.md`, `plan/session-log.md`, `plan/feature-roadmap.md`,
`plan/README.md`, `vogue-vintage-vibes/FEATURES.md`,
`vogue-vintage-vibes/DESIGN_SYSTEM.md`. `infra/README.md` unaffected (no compose,
image or env change); `vogue-vintage-vibes/README.md` unaffected (no script, stack
or setup change — it keeps no component inventory, which lives in
`DESIGN_SYSTEM.md`).

---

## How to verify

Backend (no DB needed for the unit tests):

```sh
cd backend
./.venv/bin/python -m pytest -q          # 39 passed (14 new)
./.venv/bin/python -m ruff check app tests
./.venv/bin/python tests/api_smoke.py    # live: 76 routes/checks, 0 failed
```

The smoke script now asserts, and then reverts, the availability guard: the first
catalog product is toggled to `coming_soon`, `/stock/check` must report exactly
`["not_available"]`, `/checkout` must answer `409 stock_conflict` with the same
reason, and the original availability is restored (the follow-up order succeeds
only if the revert worked).

Live checks run this session (Docker stack, `--reload`, `backend/app` bind-mounted):

| Check | Result |
|---|---|
| `?size=M` / `?size=M,L` / `?size=M&size=L` | 16 / 16 / 16 — repeated == comma |
| `?size=M,36-38` (OR within facet widens) | 20 |
| `?color=کرم` → `?color=کرم,سفید` | 14 / 14 |
| `?size=M,L&color=کرم` | 11 (AND across facets) |
| `?size=` , `?size=&color=` | 200 + full catalog (no 500) |
| `?size=ZZ` | 0 results |
| `preorder` product → `/stock/check` | `ok:false`, `reason:not_available` |
| `preorder` product → `/checkout` | 409 `stock_conflict`, `reason:not_available`, **no order written** (0 orders in the window) |
| bogus size → `/stock/check` | `reason:size_invalid` |
| inactive variant `M×کرم` on `tshirt-4` | excluded from `?size=M&color=کرم` (11 → 10), still returned for `?size=M,L&color=کرم` and `?size=M&color=کرم,شنی`, still returned with `?size=M` alone |
| cleanup | variant deleted (`204`), availability back to `in_stock`, `variants: []`, all 20 products `in_stock` |

Frontend:

```sh
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit                     # clean
./node_modules/.bin/eslint src/routes/shop.tsx src/routes/cart.tsx \
  src/routes/checkout.tsx src/lib/stock-issues.ts src/lib/api.ts   # 0 errors
```

Manual browser pass (not run this session — no dev server can start here, see
below): `/shop` → clicking two sizes keeps both chips lit and the URL carries
`size=M&size=L`; adding a colour narrows further; the count comes from the server.
Cart → item from a product the admin set to بهزودی shows «این محصول هنوز عرضه
نشده…» and «تکمیل خرید» is disabled.

---

## What is NOT done / open

- **No browser verification of the shop chips.** `vite` cannot run in this
  environment (pre-existing: Node 20.9 lacks `node:util.styleText` for rolldown;
  under nvm Node 22 the installed rolldown is missing its `darwin-arm64` binding),
  so the chip toggling is verified by `tsc` + the URL contract (`?size=M&size=L`
  reaching the API) rather than by clicking it.
- **`preorder` cannot be ordered at all** — deliberate, per the decision above;
  needs an order-level preorder flag before it can be enabled (**new task B4.13**).
- **Availability is not enforced for cart contents that are already in an order**
  path — i.e. nothing re-checks the state between `/stock/check` and `/checkout`
  beyond checkout's own gate (which is the authoritative one).
- **Facet combinations do not check variant *stock*** — a combination with an
  active variant at `stock: 0` still matches the filter (the filter answers "is
  this offered", not "is it in stock"); filtering by availability covers that need.
- **No facet counts** — the sidebar chips carry no per-facet result counts (needs a
  facet endpoint), and the tag chips still come from the cached catalog.
- **The `size_invalid` reason is a small behaviour change** for `/stock/check`
  callers that keyed off `insufficient_stock` for a missing size; both endpoints now
  report the same reason for the same input. Noted here because it is a string a
  client could have matched on.
- Nothing in `infra/` or the compose stack changed, so `infra/README.md` was left
  untouched on purpose.
