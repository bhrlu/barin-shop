# Audit — F3.5 cart stock check + F3.6 admin catalog screens (2026-09-21)

**Task (user request):** implement **F3.5** (wire the cart to
`POST /stock/check`) and **F3.6** (product-editor merchandising fields, variant
editor, inventory/low-stock screen, review moderation screen) from
`plan/frontend-tasks.md`.

Both are frontend-only: every endpoint already existed and was verified against
the running Docker backend (see *How to verify*).

---

## What was done

### F3.5 — cart validates stock through the API

1. **`api.stockCheck()` was broken and is fixed.** `POST /stock/check` takes a
   **bare JSON array** of lines (`body: list[StockCheckLine]`) but the client
   posted `{ lines: [...] }`, which FastAPI rejects with **422** — the method had
   no callers, so this was dormant. It now posts the array and returns a named
   `StockCheckResult` type. Verified: array body → `200`, old shape → `422`.
2. **`cart.tsx` runs the check on open and after every edit.** A
   `useQuery(["cart-stock", <line signature>])` keyed on
   `product:size:color:quantity` of every line (so any quantity change or removal
   re-validates, and React Query keeps the last result while the next is in
   flight). It is public, so guests are validated too.
3. **Per-line issues.** Each issue is mapped onto the offending line with Persian
   copy per reason (`not_found` / `inactive` / `insufficient_stock`, the last one
   naming the remaining count). `StockIssue` carries the product id but not the
   size/colour, so the mapping (`issuesForLines()`) attaches an issue to the single
   line of a product, and for a product in several lines only to lines its
   `available` count cannot satisfy — a valid size/colour is never flagged by a
   sibling's shortage. Documented in a comment above the helper.
4. **Checkout is blocked while the API says `ok: false`** — the «تکمیل خرید» link
   becomes an `aria-disabled` span and a warning box explains why. A failed check
   (`isError`) does **not** block: the backend re-validates in `POST /checkout`
   anyway, so a transient network error must not lock the cart.
5. **Side fix:** a cart line whose product is no longer in the active catalog used
   to render `null` — invisible and impossible to remove. It now renders a
   «محصول حذفشده» row with the issue message and a remove button.

### F3.6 — admin catalog screens

1. **Product editor merchandising fields** (`admin.products.tsx`): `tags`
   (comma-separated), `badge` (بدون نشان/حراج/جدید/ویژه/بهزودی/پیشخرید),
   `availability` (موجود/بهزودی/پیشخرید), a date input for `available_at`
   (disabled and cleared while `availability = in_stock`) and
   `low_stock_threshold`. `ProductWrite` in `api.ts` was extended to match
   `ProductIn`. The list rows now show availability + `available_at`, badge, a
   «موجودی کم» marker, and the price.
2. **New `components/admin/VariantEditor.tsx`** — per-product size × colour
   stock editor, opened from a layers button on each product row. Lists
   `GET /products/{id}/variants`, creates (`POST /products/{id}/variants`), edits
   size/colour/stock/active with an explicit save button per row (disabled until
   the row differs from the server values; saving resets the draft) and deletes
   (`DELETE /variants/{id}`). Stock input is validated as a non-negative integer on
   both paths instead of being silently coerced to `0`. Size/colour inputs are
   datalist-backed from the product's own sizes/colours, so existing values are
   suggested without preventing the API's arbitrary strings. Mutations invalidate
   the admin list, the storefront `["product", id, "variants"]`, the catalog and
   the inventory queries.
3. **New `/admin/inventory`** (`admin.inventory.tsx`): summary cards from
   `GET /admin/inventory` (products, units, inventory value, out-of-stock,
   low-stock, active variants) plus the low-stock report
   (`GET /admin/inventory/low-stock`) split into products and variants, with an
   optional threshold override that switches the query key. Zero/absent values
   render neutrally, non-zero alert counts in terracotta.
4. **New `/admin/reviews`** (`admin.reviews.tsx`): `GET /admin/reviews` with an
   all/published/hidden filter, publish↔hide via `PATCH /reviews/{id}`
   (`{status}`) and the seller reply via the same endpoint (`{seller_reply}`),
   both against the backend's `ReviewModerateIn | ReviewReplyIn` union. Product
   names come from the cached catalog; hiding/reply invalidates the admin list,
   the catalog (average rating) and that product's review list.
5. **`admin.tsx`** gained the «انبار» and «نظرات» tabs; `routeTree.gen.ts` has the
   two new routes (the TanStack plugin regenerated it while the route files were
   being added — the diff is exactly the two route entries).

---

## Files changed

| File | Change |
|---|---|
| `vogue-vintage-vibes/src/lib/api.ts` | `stockCheck` posts a bare array + returns `StockCheckResult`; `ProductWrite` gained `tags`, `badge`, `availability`, `available_at`, `low_stock_threshold` |
| `vogue-vintage-vibes/src/routes/cart.tsx` | stock query, `issueMessage()`/`issuesForLines()` helpers, per-line issues, blocked checkout, deleted-product row |
| `vogue-vintage-vibes/src/routes/_authenticated/admin.products.tsx` | merchandising form fields + list chips, variant-editor toggle per row |
| `vogue-vintage-vibes/src/components/admin/VariantEditor.tsx` | **new** — per-product variant CRUD |
| `vogue-vintage-vibes/src/routes/_authenticated/admin.inventory.tsx` | **new** — inventory summary + low-stock report |
| `vogue-vintage-vibes/src/routes/_authenticated/admin.reviews.tsx` | **new** — review moderation + seller reply |
| `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx` | «انبار» + «نظرات» tabs |
| `vogue-vintage-vibes/src/routeTree.gen.ts` | two generated route entries |

Docs updated in the same session: `plan/frontend-tasks.md`, `plan/session-log.md`,
`plan/feature-roadmap.md`, `plan/README.md`, `vogue-vintage-vibes/FEATURES.md`,
`vogue-vintage-vibes/DESIGN_SYSTEM.md`. `backend/README.md`,
`infra/README.md` and `vogue-vintage-vibes/README.md` were **not** touched — no
endpoint, setup step, script or stack change (see *What is NOT done / open*).

---

## How to verify

Static checks (no backend needed):

```sh
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit          # clean
./node_modules/.bin/eslint src/routes/cart.tsx \
  src/routes/_authenticated/admin.products.tsx src/routes/_authenticated/admin.tsx \
  src/routes/_authenticated/admin.inventory.tsx src/routes/_authenticated/admin.reviews.tsx \
  src/components/admin/VariantEditor.tsx src/lib/api.ts   # 0 errors
```

`vite build` **cannot run in this environment** (pre-existing): with Node 20.9
rolldown needs `node:util.styleText` (Node ≥ 20.12), and under nvm Node 22 the
installed `rolldown` is missing its `darwin-arm64` native binding. Neither is
caused by this change; `tsc` is the type-level equivalent that ran clean.

Against the running stack (Docker backend on `:8000`), all shapes the new UI
reads were exercised:

```sh
PID=$(curl -s localhost:8000/products | jq -r '.[0].id')
# bare-array body works, the old {lines:…} shape is 422 (proves the api.ts fix)
curl -s -X POST localhost:8000/stock/check -H 'Content-Type: application/json' \
  -d "[{\"product_id\":\"$PID\",\"size\":\"\",\"color\":\"\",\"quantity\":1}]"
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@sande.local","password":"admin1234"}' | jq -r .access_token)
curl -s localhost:8000/admin/inventory -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/admin/inventory/low-stock -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/admin/reviews -H "Authorization: Bearer $TOKEN"
```

Results: `stock/check` → `{"ok":true,…}` for a real size/colour and `422` for the
old shape; `/admin/inventory` → `{totalProducts:20,totalUnits:465,…}`;
`/admin/inventory/low-stock` → 1 product (`tshirt-1`, stock 1) and 0 variants;
`/admin/reviews` → review rows with `status`, `author_name`, `seller_reply`. The
variant CRUD and review moderation/reply paths were exercised end-to-end with a
**temporary** variant and review that were deleted again (both `204`; verified
afterwards that `GET /products/tshirt-4/variants` is `[]` and a storefront
`stock/check` is `ok: true` again), so the dev DB keeps no throwaway rows.

In the browser (not done headlessly — see below): add an item, open `/cart`,
lower the stock of that combination in `/admin/products` (layers button), reload
the cart → the line shows «فقط … عدد …» and «تکمیل خرید» is disabled; as admin open
`/admin/inventory` and `/admin/reviews` and edit a variant / hide a review /
post a reply.

---

## What is NOT done / open

- **No headless-browser click-through.** The audit above reasoned from
  `tsc`/eslint plus live API responses; the rendered cart/admin screens were not
  driven in a browser this session, so visual/layout regressions (RTL spacing in
  the new admin grids, the disabled checkout state) are unverified by eye.
- **Cart stock is not re-checked on window focus** — a cart left open keeps the
  result of its last edit. `POST /checkout` re-validates server-side, so this can
  only be stale UI, never a wrong order. Logged as **F3.5b** in the task file.
- **No cart-side quantity capping** from the reported `available` — the message
  tells the customer to reduce the quantity; the + button still goes to 20.
- **Availability is still UI-only on the backend** (`coming_soon`/`preorder` pass
  `stock/check` and checkout) → unchanged, still **B4.11**.
- **Admin screens are unpaginated** (they load every product/review, as before) and
  the reviewer's product link goes to the storefront page, not an admin detail
  view → **F2.5**.
- **Review replies can't be cleared** — `ReviewReplyIn` requires `min_length=1`;
  the form can only overwrite. Not logged as a task yet.
- **No "delete review" from the admin screen** (the endpoint exists and the
  customer-facing delete is used in `ReviewsSection`) — moderation is hide/publish
  only, which keeps an audit trail.
- **Out of scope:** no coupon admin screen and no refund-requests screen
  (**F2.4**), no charts (**F2.6**) — untouched, as they were not part of F3.6.
- `backend/README.md` / `infra/README.md` / `vogue-vintage-vibes/README.md`
  untouched: no endpoint, env var, script or setup step changed (the frontend
  README has no route inventory to update).
