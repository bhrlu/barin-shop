# Audit — F3.5b Re-check cart stock on window focus (2026-09-23)

## Task

`F3.5b` (P2, Batch D). A cart left open keeps its last `POST /stock/check` result.
Required: re-run the stock check when the cart window regains focus. Checkout's
server-side validation stays the final authority. Part of the "continue the whole
backlog" run.

## Spec check (Rule 0)

No spec section covers cart stock revalidation. `B1` holds: no copy or layout change.
The existing banner and disabled button are reused. The stack header is ignored as
always.

## Recon / contract (Rules 6–10)

- Owning module: `routes/cart.tsx`. It holds the `["cart-stock", <cart signature>]`
  query, which is enabled only with lines, and derives the per-line issues, the
  banner and the blocked checkout button from it.
- **Measured before the change** (Playwright, stock lowered behind an open cart):
  - React Query v5 (`^5.101`) already refetches stale queries on `visibilitychange`,
    so a **tab switch** re-checked.
  - Its focus manager does **not** listen to `window` `focus`. Coming back to the
    window without the tab being hidden (alt-tab from another app, side-by-side
    windows, a devtools/popup window) left the stale result: 0 requests, no banner,
    checkout still allowed.

  The backlog wording ("keeps its last result until an edit") was therefore true
  only for the window-focus case.
- Contract unchanged: same `POST /stock/check` body and response. No backend change.
- Security/state: read-only. The blocked button is UI only, because `POST /checkout`
  re-validates stock in the same transaction that reserves it. A second focus while a
  check is in flight must not double the request (R10 "runs twice").

## What was done

`routes/cart.tsx` adds a `focus` listener while the cart has lines. It calls
`stock.refetch({ cancelRefetch: false })`:

- **`cancelRefetch: false`:** the call joins a check already in flight. A tab switch
  fires `visibilitychange` (React Query's own refetch) and then `focus`; without this
  option the second event cancelled and repeated the first request.
- **Guard on "has lines":** `refetch()` ignores `enabled`, so without it an empty cart
  would `POST /stock/check []` on every focus (422 plus a retry).

The global `focusManager` was left alone, so no other query in the app gains a new
refetch trigger (R12).

## Files changed

- `vogue-vintage-vibes/src/routes/cart.tsx`
- docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`

## How to verify

Browser script (Playwright against the running stack; stock changed with the admin
API and restored in `finally`): 15 checks, 0 failed.

1. A cart holding 5 is open and checkout is allowed. Stock is lowered to 2. Nothing
   changes while the window stays unfocused.
2. **Window `focus`:**
   - exactly one `POST /stock/check`;
   - the banner «موجودی این اقلام تغییر کرده است» appears;
   - «تکمیل خرید» is disabled.
3. Stock is restored. **Tab switch** (`visibilitychange` hidden→visible, then `focus`
   as a separate task): exactly **one** request, the banner goes and the checkout
   link comes back.
4. Empty cart (after hydration): focus makes **no** request.
5. Stock is back to its original value and there are no page errors.

Negative controls (each run with the same script):

| Variant | Result |
| --- | --- |
| `HEAD`'s `cart.tsx` | 4 fail: focus makes no request, no banner, checkout not blocked |
| without `cancelRefetch: false` | 1 fails: the tab switch makes 2 requests |
| without the has-lines guard | 1 fails: the empty cart posts on focus |

The first version of the script dispatched non-bubbling `visibilitychange` events and
checked the empty cart before hydration, so two of these controls passed. Both gaps
were fixed before the results above.

Gates (frontend container):

- `prettier --check` clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / 16 warnings (unchanged);
- `bun run build` OK.

No backend or infra change, so pytest, the smoke test and a clean environment are not
needed.

**Verification level:** browser tested.

## What is NOT done / open

- `/checkout` does not show availability before submit (a stock conflict there
  surfaces as a toast from `POST /checkout`). Adding a pre-submit check there is not
  part of F3.5b.
- The cart's display prices (`useCartSubtotal`, `staleTime` 60 s) are not re-read on
  focus. The server recomputes the total at checkout.
- `README.md`, `FEATURES.md`, `feature-roadmap.md`, `DESIGN_SYSTEM.md`: untouched —
  no capability, setup or UI convention changed.
