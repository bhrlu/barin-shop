# Audit — F5.11 `/shop` leaks invalid URL params to the API (2026-09-23)

## Task

`F5.11` (P3, Batch D), found during AB-FE-05. TanStack Router merges a route's
validated search over the parent's raw one, so a key that `validateSearch` *omits*
survives with its raw value. `/shop?page=abc` sent `page=abc` (a 422, retried, no
products); `?category=hack` filtered on it. Required: return rejected keys as explicit
`undefined`, as AB-FE-05 did in `admin.products.tsx`. Part of the "continue the whole
backlog" run.

## Spec check (Rule 0)

No spec section covers URL validation. `B1` holds: nothing visual changes. Nothing is
in conflict.

## Recon (Rules 6–8)

`routes/shop.tsx` `validateSearch` built its result from conditional spreads
(`...(ok ? { key } : {})`), which omit every rejected key.

**Reproduced on the old code** (Playwright), request by request:

| URL | Sent to the API | Result |
| --- | --- | --- |
| `?page=abc` | `page=abc` | 422 ×2, 0 products |
| `?category=hack` | `category=hack` | 0 products |
| `?sort=evil` | `sort=evil` | 422 |
| `?badge=zzz` | `badge=zzz` | 0 products |
| `?availability=never` | `availability=never` | 0 products |
| `?maxPrice=-5` | `max_price=-5` | 422 |

The same omission would also let `size` / `color` / `tag` / `q` / `onSale` through.
For example, `?onSale=maybe` would reach the page as truthy.

The API contract is unchanged; this change only affects which values the page sends.

## What was done

- `validateSearch` returns **every** key, each either a valid value or an explicit
  `undefined`.
- `page` must now be a positive integer.
- `ShopSearch`'s keys are typed `T | undefined` (needed under
  `exactOptionalPropertyTypes`).
- The link builder `clean()` already drops `undefined`, so URLs stay tidy.

## Files changed

- `vogue-vintage-vibes/src/routes/shop.tsx`
- docs: `vogue-vintage-vibes/FEATURES.md` (۱.۲), this audit, `plan/MASTER-BACKLOG.md`,
  `plan/frontend-tasks.md`, `plan/session-log.md`, `plan/README.md`

## How to verify

Browser (Playwright): **8 checks, 0 failed**.

- For each of the six URLs above: the invalid value is not sent, there is no 4xx, and
  products are shown.
- Valid `?category=tshirt&page=1&sort=price_asc&size=M` still reaches the API
  intact.
- No page errors.

**Negative control:** the same script on the old file fails the 6 invalid-URL checks
(the table above).

**Regression:** F5.8's `/shop` suite (filters, chips, pager, search) passes 23/23.

Gates:

- `prettier`, `tsc` clean;
- `bun run lint` 0 errors / 14 warnings;
- `bun run build` OK.

**Verification level:** browser tested.

## What is NOT done / open

- An invalid value stays visible in the address bar. The page ignores it, and the
  URL is cleaned the next time a filter link is followed. Rewriting the URL on load
  was not needed.
