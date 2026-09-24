# Audit — 2026-09-25 · F5.19 Admin inventory ledger viewer

## Task

Close the last F5.19 gap: the ledger screen on `/admin/inventory` already showed
the ledger with a reason filter, but the original requirement — **reason chips
and a real product filter** — had only the contextual history links, no generic
product filter control.

## Spec check (Rule 0)

- `[FE-02]` (admin data table): the ledger stays an `AdminDataTable`; the new
  control sits in `toolbarEnd` (the component's documented toolbar slot) rather
  than becoming a second table abstraction (D8 respected).
- `[BE-01]` (variants & inventory): the filter reads the existing
  `inventory_logs` path only; no second inventory accounting.
- Followed: Rules 0–5; Part B 6, 6a, 7, 8, 9, 12, 13, 15 (10/11 not triggered —
  the change reads the ledger, moves no money/stock).
- Deliberately ignored: none. The spec was not edited.

## What was done

1. **Product filter (the gap).** New `ProductFilter` combobox inside
   `admin.inventory.tsx`: Popover + Command (the repo's existing combobox
   pattern, as in `HeaderSearch`), backed by the canonical `GET /search?q=`
   through `api.search(q, 8)` — server-side, limit 8, debounced 300 ms; the
   catalogue is never downloaded. Selecting a hit sets `product_id` (clearing
   `variant_id`); the clear action removes both. Rendered via
   `AdminDataTable`'s `toolbarEnd` prop; the reason chips are untouched, as are
   the product/variant history links (which still reuse the same URL state).
2. **Invalid URL values.** `validateSearch` now validates `product_id` /
   `variant_id` against a UUID pattern (F5.11's "invalid values never reach the
   API" convention): junk is stripped and the router redirects (307) to the
   clean URL.
3. **No backend change.** Verified the existing contract: `GET
   /admin/inventory/logs` stays `StaffCatalog`-guarded, same page envelope
   (`items/total/page/page_size/pages`), `product_id` filter already supported,
   `reason` is a server-side `Literal` (422 on junk). Zero backend edits; no
   new endpoint; no `api.ts` change (the `product_id` query param was already
   built).
4. **Filter state semantics.** Any filter/page change routes through
   `setSearch`, so the product filter survives pagination and is shareable via
   URL; "نمایش همه" (scope banner) and the new "همه" (toolbar) both clear.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/admin.inventory.tsx` (the
  product filter + UUID validation; rest of the screen preserved as-is)
- `plan/frontend-tasks.md` (F5.19 ticked)
- `plan/MASTER-BACKLOG.md` (F5.19 → DONE in JSON + prose, §20 counts/pointer)
- `plan/session-log.md` (appended)
- `plan/audit/2026-09-25-f519-admin-inventory-ledger-viewer.md` (this file)

## How to verify

- Lint: `cd vogue-vintage-vibes && bun run lint` → 0 errors (14 pre-existing
  warnings in other files).
- Build: `bun run build` (Node ≥ 20.12 required; system node 20.9 breaks
  `util.styleText` — nvm v22 used) → exit 0.
- Backend: `pytest -q` → **353 passed** (incl. the 9 `test_inventory_log.py`
  tests: envelope, product/reason filters, 422 junk reason, 403 support/customer,
  401 anonymous, net-zero checkout→cancel).
- Smoke: `./.venv/bin/python tests/api_smoke.py` → **257 routes/checks, 0 failed**.
- Runtime: `/admin/inventory` → 200; `/admin/inventory?product_id=not-a-uuid`
  → 307 redirect (junk stripped before any API call).

## What is NOT done / open

- **Browser verification (interactive)**: no frontend test runner exists and no
  browser session was available in this environment; the acceptance flow
  (checkout → cancel → two rows netting to zero → support 403) is verified at
  the API level by `test_inventory_log.py` (`test_checkout_and_cancel_net_to_zero`,
  `test_the_read_endpoint`) and the smoke run, and the route renders (200), but
  the combobox was not clicked through in a real browser. Verification level:
  **integration tested + build-verified** — one step below the repo's "fully
  verified".
- Pre-existing environment issues encountered and fixed locally, unrelated to
  this feature: stale `node_modules` (missing `@tanstack/react-table`,
  restored via `bun install --frozen-lockfile`) and system node 20.9 being too
  old for the build toolchain.
