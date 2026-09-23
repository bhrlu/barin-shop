# Audit — F5.12 Cart provider loads the whole catalogue on every route (2026-09-23)

## Task

`F5.12` (P2, Batch D), discovered as `NEW-ABFE05-3` during AB-FE-05:
`CartProvider` (mounted in `__root.tsx`, so on every route, admin included) ran
`catalogQuery` — `GET /products?include_inactive=true`, every product — only to
compute the cart's display `subtotal`. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

The spec has no section on the cart provider or on request budgets. `B1` (no visual
change, Persian copy) holds: nothing on screen changes. The coupon signature in the
spec's `validateCoupon({ code, cartTotal, userId })` is the stale Supabase-era shape.
This repo's `POST /coupons/validate {code, subtotal}` is untouched. The stack header
(Supabase) is ignored as always, and the cart money rules (۸۹٬۰۰۰ shipping, free ≥
۲٬۰۰۰٬۰۰۰) are unchanged.

## Recon / contract (Rules 6–8, 11)

- Owning module: `src/lib/cart.tsx` (the canonical cart state, R7).
- `useCart()` consumers:
  - `SiteHeader` (`count`);
  - `product.$id.tsx` (`add`);
  - `routes/cart.tsx` (`lines, subtotal, setQuantity, remove`);
  - `routes/checkout.tsx` (`lines, subtotal, clear`).
- **Only cart and checkout read `subtotal`**, and both already call `useCatalog()`
  themselves to render product names and images.
- No API contract changes. The subtotal is display-only. The server still recomputes the
  authoritative total at `POST /checkout` (`services/pricing.py`), and
  `POST /stock/check` stays the cart's stock authority. The coupon check still sends
  the same `subtotal` value.
- Other `useCatalog()` users (`/`, `/shop`, `/account/favorites`,
  `/admin/reviews`) render the catalogue themselves. They keep loading it by design;
  `/shop`'s duplicate fetch is F5.8.

## What was done

- `CartProvider` no longer runs a query. Its context is now `lines`, `count`, `add`,
  `setQuantity`, `remove` and `clear`, so there is no `subtotal`.
- New `useCartSubtotal()` in `src/lib/cart.tsx` uses the same formula as before
  (catalogue price × quantity, unknown products skipped) and the same
  `catalogQuery` + `staleTime: 60_000`. Only `routes/cart.tsx` and
  `routes/checkout.tsx` call it, so the catalogue loads only when a page that shows a
  subtotal is opened. This is the backlog's "defer until the cart is used" option;
  fetching only the cart's product ids would not save anything, because those two
  pages load the full catalogue through `useCatalog()` anyway.

## Files changed

- `vogue-vintage-vibes/src/lib/cart.tsx`
- `vogue-vintage-vibes/src/routes/cart.tsx`
- `vogue-vintage-vibes/src/routes/checkout.tsx`
- docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`

## How to verify

Browser script (Playwright against the running compose stack): 27 checks, 0 failed.

1. With a 2-item cart stored, a full load of `/admin/products`, `/admin/orders`,
   `/account`, `/product/<id>`, `/about` and `/contact` makes **0** catalogue
   requests. The header badge still shows ۲.
2. Detector control: `/` and `/admin/reviews` still make ≥ 1 catalogue request (they
   render it).
3. SPA navigation from `/admin/orders` to `/cart` fetches the catalogue on demand. The
   subtotal is price × 2 and the total is subtotal + shipping.
4. A temporary coupon (10 %) is applied on the cart page. The discount row shows the
   server's discount, and the total is subtotal − discount + shipping.
5. Stock issue: a product's stock is lowered to 2 and the cart holds 5. The banner
   shows and «تکمیل خرید» is disabled. Stock is restored afterwards.
6. Checkout as a fresh customer:
   - `/checkout` loads the catalogue;
   - the displayed total is price + shipping;
   - `POST /checkout` returns 200 and the page navigates to `/payment/…`;
   - the server's order total equals the displayed total;
   - the cart badge clears.

   The order is then cancelled (stock back to 25 on every seed product) and the
   coupon deleted.
7. No page errors.

**Negative control:** the same script was run with the three files swapped back to
`HEAD`. All six "no catalogue request" checks **fail** (1 request each); the other 21
checks pass. The files were then restored.

Gates (in the frontend container):

- `prettier --check` (changed files) clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / 16 warnings. It was 15; the +1 is
  `react-refresh/only-export-components` on the new `useCartSubtotal` export. That rule
  already flags `useCart` in the same file, and `auth.tsx` / `compare.tsx` follow the
  same hook-next-to-provider idiom.
- `bun run build` OK.

No backend change, so pytest, the smoke test and a clean environment are not needed
(R13/R14).

**Verification level:** browser tested.

## What is NOT done / open

- `/shop` still requests the catalogue *and* the filtered page. That is **F5.8**
  (next).
- Cart and checkout still load the full catalogue to render lines. A per-id product
  endpoint for the cart would be a separate task. It is not needed for F5.12, which
  was about every other route.
- `README.md`, `FEATURES.md`, `feature-roadmap.md`, `DESIGN_SYSTEM.md`: untouched —
  no capability, setup, token or component convention changed.
