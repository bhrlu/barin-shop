# Audit — 2026-09-20 — Frontend F3.2 Product page (variants, reviews, rails, availability)

**Task:** `plan/frontend-tasks.md` → Milestone F3 §F3.2 — rebuild
`product.$id.tsx` around the catalog backend: variant picker with
per-combination stock, reviews & ratings UI, related + recommended carousels,
view tracking, availability states (`coming_soon` / `preorder` + `available_at`)
and `tags` / `badge` display.

Pre-flight: every endpoint used here was already live and smoke-verified
(`GET /products/{id}`, `/variants`, `/reviews`, `related`, `/recommendations`,
`POST /products/{id}/view`) and F3.0 had wrapped them in `src/lib/api.ts`.
`DESIGN_SYSTEM.md` was read first; the new UI follows it (Persian/RTL, `@/`,
`cn()`, sand/terracotta/sage/clay tokens, `toFa`, TanStack Query, `sonner`,
existing `ui/*` primitives).

## Files changed

| File | Change |
|---|---|
| `vogue-vintage-vibes/src/routes/product.$id.tsx` | Rewritten. Fetches the product with `GET /products/{id}` (no longer `useCatalog().byId`), renders badge/discount/tags, availability states, the variant picker, quantity + add-to-cart, and the two rails + reviews section. `key={product.id}` on the detail child resets gallery/selection state when the param changes; inactive products now render the «محصول یافت نشد» view. |
| `vogue-vintage-vibes/src/components/product/VariantPicker.tsx` | **New.** Colour swatches + size buttons driven by effective per-combination stock: a size is disabled when its combination is deactivated/empty, a colour whose every size is dead is disabled (and labelled «ناموجود»), and an `aria-live` line reports «فقط N عدد باقی مانده» / «این ترکیب سایز و رنگ موجود نیست». Changing colour clears a size that is no longer purchasable. |
| `vogue-vintage-vibes/src/components/product/ReviewsSection.tsx` | **New.** Rating summary (average, count, 1–5 distribution bars), published review list with seller replies and Jalali dates, and a write/edit form: star input, title, body, `POST /products/{id}/reviews` (backend upserts one review per customer), delete own review, pre-filled from the customer's existing review; guests get a sign-in link with `?redirect=/product/{id}`. |
| `vogue-vintage-vibes/src/components/product/ProductRail.tsx` | **New.** RTL carousel rail (shadcn `ui/carousel` + embla, `direction: "rtl"`) with header arrow buttons that track `canScrollPrev/Next`, used for both «محصولات مرتبط» and «پیشنهاد برای شما». |
| `vogue-vintage-vibes/src/lib/variants.ts` | **New.** `comboStock` / `variantStockFor` / `defaultColor` — the storefront mirror of the backend's `app/services/variants.py` (explicit variant wins for its size×color; `active: false` disables the combination; otherwise the product aggregate applies), including `soldOut`. |
| `vogue-vintage-vibes/src/lib/catalog.ts` | Added `toProducts()` (maps + signs a list of rows), `productQuery`, `variantsQuery`, `reviewsQuery`, `relatedQuery`, `recommendationsQuery`; `catalogQuery` now reuses `toProducts()`. |
| `vogue-vintage-vibes/src/lib/format.ts` | Added `formatFaDate()` — Persian (Jalali) dates via `Intl.DateTimeFormat("fa-IR-u-ca-persian")`, wrapped in `toFa` so digits stay Persian even if ICU falls back. |

No backend change was needed; the only backend gap found is logged below.

## How to verify

```bash
cd vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit -p tsconfig.json            # clean
./node_modules/.bin/eslint src/routes/product.\$id.tsx src/components/product/ \
  src/lib/variants.ts src/lib/catalog.ts src/lib/format.ts   # clean
```

Browser (stack up: backend `:8000`, frontend `:5173`):

1. `/product/tshirt-1` → badge «جدید», «٪۲۲ تخفیف», tag chips `#اورسایز #پنبه
   #روزمره`, hint «برای دیدن موجودی، سایز را انتخاب کنید» and a **disabled
   «انتخاب سایز»** button; pick a size → hint «فقط ۱ عدد باقی مانده» and the
   button becomes «افزودن به سبد خرید»; clicking it writes
   `sandeh-cart-v1` and bumps the header badge to «۱».
2. Rails render («محصولات مرتبط» = 3 same-category products, «پیشنهاد برای شما»
   = 8 slides) and `/product/crop-7` shows the published review with the summary
   «۵.۰ از ۵ · از ۱ نظر ثبتشده», the 1–5 distribution and the review text.
3. `/product/crop-5` → «هیچ امتیازی ثبت نشده» + the signed-out prompt.

Verified here with headless Chrome over the DevTools pipe protocol (temporary
scripts, since deleted) — all of the above, plus the state-dependent paths with
**temporary demo data** (see below):

| State | Result |
|---|---|
| Variant with `active: false` (L / سفید شکسته) | size button `L=DISABLED`, clicking it changes nothing |
| Variant with `stock: 0` (XS / شنی) | `XS=DISABLED` once شنی is selected; the previously chosen size is cleared |
| Variant with `stock: 2` (M / سفید شکسته) | hint «فقط ۲ عدد باقی مانده»; five «+» clicks clamp the quantity at «۲» |
| Every size of a colour dead (زغالی) | swatch renders disabled with `aria-label="زغالی — ناموجود"` |
| `availability: coming_soon` + `available_at` | chip «بهزودی», note «این محصول از ۲۳ مهر ۱۴۰۵ عرضه میشود.», button «بهزودی» disabled |
| `availability: preorder` + `available_at` | chip «پیشخرید», note «پیشخرید تا ۱۰ آبان ۱۴۰۵؛ پس از عرضه ارسال میشود.», button «پیشخرید» disabled |

**Demo data was written to the dev DB with explicit user approval and then
reverted** (8 variants created through `POST /products/{id}/variants`, two
products temporarily patched, then variants deleted and both products restored):
final state re-checked as `variants=0`, `availability=in_stock`,
`available_at=None` for all 20 products — i.e. exactly the state before this
task. The temp scripts were deleted.

## What is NOT done / open

- **Backend does not enforce `availability`.** `app/services/checkout.py`
  validates stock/activity/size but ignores `coming_soon`/`preorder`, so a
  hand-crafted API call could still order a not-yet-released product; the UI
  blocks it, the API does not. Logged as **B4.11** in `backend-tasks.md`.
- **Cart does not re-check per-variant stock** when opening/updating the cart —
  that is F3.5 (`POST /stock/check`).
- The product page is **not SSR-prefetched** (same as the rest of the store):
  first paint shows the skeleton, hydration fills it.
- **Ratings were not added to `ProductCard`** (`avg_rating`/`review_count`) — F3.3.
- The colour/size picker is a full cross-product: a size stays selectable when
  the current colour has a variant for it even if the aggregate product is empty
  — the effective rule is always the backend's (variant wins), and the button is
  disabled whenever that combination is not purchasable.
- Products with `active: false` are now hidden on the storefront product URL as
  well (previously an admin browsing the catalog could open them by id); admins
  still manage them in the admin product list.
- `ProductRail` RTL gutters use `ml-0 -mr-4` to counter the primitive's
  LTR-oriented `-ml-4/pl-4`; verified by DOM/state only, not by pixel diff.
- Docs deliberately untouched: `vogue-vintage-vibes/README.md` (no setup/stack
  change), `backend/README.md` and `infra/README.md` (no backend or infra change),
  `plan/RULES.md`.
