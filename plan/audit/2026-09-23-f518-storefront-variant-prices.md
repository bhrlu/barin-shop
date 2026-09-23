# Audit — F5.18 Storefront shows variant price overrides (2026-09-23)

## Task

`F5.18` (P2, Batch D), found during AB-BE-02. Since AB-BE-02 the server prices a
line with the variant's `price_override`, but the storefront did not show it:

- the product page showed `products.price` for every size and colour;
- the cart and checkout multiplied catalogue prices (`useCartSubtotal`, F5.12);
- the cart sent that subtotal to `/coupons/validate`.

The shown total could therefore differ from the charged one. F5.18 blocks AB-FE-03's
price field. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

- **Followed:**
  - `B1` (Persian copy; a skeleton while an amount loads);
  - R11 / `B1`'s "the backend is authoritative for money": the storefront now
    displays the server's prices instead of computing them.
- **Ignored:** the stack header.

## Recon / contract (Rules 6–11)

**Price consumers.**

- The product page renders `product.price`.
- `routes/cart.tsx` and `routes/checkout.tsx` render `product.price × qty` per line
  and `useCartSubtotal()` for the summary.
- The cart already calls `POST /stock/check` on every cart change, and that call
  returned a server `subtotal`, but no per-line prices.

**Why a backend addition.** A per-line price without N variant requests needs one
server source. `StockCheckOut` gains `unit_prices: (int|null)[]`: the server unit
price per request line, **in request order**, from `variant_price()` (AB-BE-02).
`null` means an unknown product. A line with an issue (sold out, inactive) is still
priced. The change is additive: existing fields are unchanged, and older clients
ignore the new one.

**Design.** The subtotal stays the server's `subtotal`. The frontend adds nothing.
With a blocked line it shows the buyable subtotal, next to the existing "stock
changed" banner.

## What was done

- **Backend:**
  - `schemas.StockCheckOut.unit_prices`;
  - `routers/stock.py` fills it for every line.
  - Test: `test_stock_check_returns_each_lines_server_unit_price` covers an override,
    no variant row, a sold-out variant, an unknown product and a plain product. It
    also checks that the subtotal counts only buyable lines.
- **`src/lib/cart.tsx`:** `useCartSubtotal` (catalogue prices) is replaced by
  **`useCartQuote()`**, the one shared quote query:
  - key `["cart-stock", <lines>]`, the same as before;
  - `placeholderData: keepPreviousData`, so the previous quote stays on screen during
    a re-quote, as the old comment already claimed;
  - `priceOf(line)` looks prices up by product|size|colour, never by position.

  The key helper is module-private, so there is no new export and the lint count is
  unchanged.
- **`routes/cart.tsx`:**
  - the stock query now comes from `useCartQuote()`;
  - each line total is `priceOf(line) × qty`, and the subtotal is the quote's;
  - shipping and total derive from that subtotal;
  - amounts still loading show a skeleton, and a failed quote shows «—»;
  - «ثبت» (coupon) is disabled until there is a quote, and the coupon is validated
    against the quote's subtotal;
  - the F3.5b focus re-check is unchanged.
- **`routes/checkout.tsx`:** the same quote (shared cache) for line totals, shipping
  and total, with the same skeleton / «—».
- **`routes/product.$id.tsx`:**
  - once a size is chosen, the price is that size×colour's `price_override` or the
    product price;
  - the discount badge and struck-through `oldPrice` compare against that price, and
    the strike shows only when `oldPrice` is higher;
  - a `data-testid="product-price"` hook was added.
- **`src/lib/api.ts`:** `StockCheckResult.unit_prices`.

## Files changed

- `backend/app/schemas.py`, `backend/app/routers/stock.py`,
  `backend/tests/test_variant_fields.py`
- `vogue-vintage-vibes/src/lib/cart.tsx`, `src/lib/api.ts`, `src/routes/cart.tsx`,
  `src/routes/checkout.tsx`, `src/routes/product.$id.tsx`
- docs:
  - `backend/README.md` (stock-check row, "Variant price");
  - `vogue-vintage-vibes/FEATURES.md` (rows ۱.۳ and ۱.۵);
  - this audit;
  - `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/session-log.md`,
    `plan/README.md`.

## How to verify

**Backend:**

- `pytest tests/test_variant_fields.py tests/test_variants.py`: 18 passed.
- `pytest -q` 230 passed, `ruff` clean, smoke 235/0.

**Browser** (Playwright on the Docker stack): **11 checks, 0 failed**. Setup: a
product at 100 000 with variants M (override 80 000) and L (none), plus a plain
seeded product in the cart and a temporary 10 % coupon.

- **Product page:** 100 000 before a size is picked, M → 80 000, L → 100 000.
- **Cart:**
  - line totals: M×2 = 160 000, L×1 = 100 000, the plain product = its price;
  - the subtotal equals the server quote;
  - `/coupons/validate` is sent the overridden subtotal and returns 10 % of it;
  - M → ×3 re-quotes the subtotal.
- **Checkout:** total = subtotal + shipping. The order is placed, and **the server
  charged exactly what was shown**. The order is then cancelled and the coupon and
  product deleted.
- No page errors.

**Negative control:** `HEAD`'s five frontend files with the new backend. 6 fail:

- the product page shows 100 000 for M;
- cart subtotal 940 000 vs the server's 900 000;
- line totals `[200000, …]`;
- the coupon is quoted on 940 000;
- the re-quote check;
- checkout shows 1 029 000 for an order charged 989 000.

**Regression** (the cart page's query changed): F5.12's suite 27/27 and F3.5b's
suite 15/15.

Gates:

- `prettier` / `tsc` clean;
- `bun run lint` 0 errors / 14 warnings (unchanged);
- `bun run build` OK.

**Verification level:** browser tested.

**Process note.** During the negative control, the backup loop named copies by
`basename`. `src/lib/cart.tsx` and `src/routes/cart.tsx` share a basename, so the
restore wrote the cart **page** into `lib/cart.tsx`. This was caught by the
oversized diff. `lib/cart.tsx` was rebuilt from `HEAD` plus the same edits, and every
result above (F5.18, F5.12, F3.5b, tsc, lint, build, pytest, smoke) was re-run
afterwards.

## What is NOT done / open

- **Listing prices.** Product cards and the shop grid still show the product's base
  price; a "from" price for variants with overrides was not added.
- **Checkout discount.** The checkout summary still does not show a coupon discount.
  The server applies it (existing behaviour).
- `DESIGN_SYSTEM.md`, `feature-roadmap.md`: untouched.
