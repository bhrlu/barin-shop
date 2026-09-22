# AB-FE-02 — Admin export controls

**Date:** 2026-09-22 · **Task:** `AB-FE-02` (P1, Batch B, `plan/MASTER-BACKLOG.md`;
from `[FE-02]` toolbar export + `[BE-08]`; full-backlog audit §AB-FE-02) ·
**Layer:** frontend, plus one backend CORS line the contract needed

## Task

B2.2 shipped `/admin/export/orders.{csv,xlsx}`, `/admin/export/products.{csv,xlsx}`
and `/admin/export/report`, but no screen reached them (full-backlog audit
"Drift 5": the buttons had been parked behind the unbuilt F4.3 data grid). AB-FE-02
adds visible export controls with correct authenticated download handling, date and
status filters, loading and error states, and capability guards, without waiting
for F4.3.

## Spec check (Rule 0)

Followed:

* **[FE-02]** "CSV/Excel export on the far side" of the list toolbar. There is no
  data-grid toolbar yet (F4.3), so the controls sit in a toolbar card above the
  orders list and next to «محصول جدید» on the products page.
* **[BE-08]** `exportOrders({ fromDate, toDate, status?, format })`: the orders
  panel exposes exactly those four inputs.
* **B0.2 / B1.1** — semantic tokens only. Errors use `text-destructive`
  (DESIGN_SYSTEM §2.3, repo wins over spec B0.2's palette classes).
* **B0.4** — `rounded-2xl` card with `border-border/60 shadow-sm`; `rounded-xl`
  fields and buttons.
* **B0.5 / B4.3** — pulse skeleton for the report and Sonner success toast;
  "preparing…" label on the running button instead of a spinner.
* **B1.4 / B1.5 / B1.6** — Persian labels and messages, Persian digits and
  `formatToman` in the report, Jalali preview of the chosen range; 375 px checked.
* **[FE-01].3** — support/customer direct URL entry keeps the Persian permission
  notices (no export controls render, no export request fires).

Deliberately not followed:

* **[FE-02] as a reusable `AdminDataTable`** — that is F4.3, excluded from this task.
  The backlog says explicitly "Do not wait for F4.3".
* **Jalali date picker** — none exists in the repo, and adding one is a dependency
  decision. The native `<input type=date>` is Gregorian, so the Jalali reading of
  the range is printed under the fields.
* **Spec stack wording** (`exportOrders` as an RPC / server function) — stale; it
  is a FastAPI GET.

## Architecture check (Rules 6–11)

* **Owning modules:** `src/lib/api.ts` (HTTP + contract quirks),
  `src/components/admin/ExportControls.tsx` (new, spec B2 directory),
  `admin.orders.tsx` / `admin.products.tsx` (mount points),
  `backend/app/main.py` (CORS).
* **Data flow:** button → `api.adminExportOrders/adminExportProducts` →
  `requestFile()` → `backend/app/routers/exports.py` → `services/exports.py` →
  Postgres. The report goes `api.adminSalesReport` → `request()` → the same router.
* **Contract (verified live):**
  * `GET /admin/export/orders.{csv|xlsx}?from=&to=&status=` and
    `GET /admin/export/products.{csv|xlsx}` return a file with
    `Content-Disposition: attachment; filename="sande-…-YYYYMMDD-HHMM.ext";
    filename*=UTF-8''<Persian name>`.
  * `GET /admin/export/report?from=&to=` → `{from, to, daily[], monthly[],
    bestSellers[]}` (JSON, bare object).
  * Guard `StaffOrders` = `{admin, super_admin, order_manager}`. 401 anonymous,
    403 without the capability, 422 on an unparsable or inverted range (English
    detail).
  * `from` defaults to 30 days back; `status` is an optional order-status string.
* **Two contract quirks the UI had to respect (found in recon):**
  1. `to` is **exclusive** (`created_at < :to_ts`). A plain date for "to = today"
     would silently drop today's orders.
  2. `parse_range` uses `.replace(tzinfo=UTC)`, which **discards** any offset:
     `2026-09-22T00:00:00+03:30` is read as UTC midnight.
  So `exportRange()` in `api.ts` sends local midnight of `from` and local
  midnight of the day after `to`, both as offset-less UTC ISO strings. In
  Asia/Tehran, 24 Aug → 22 Sep becomes `2026-08-23T20:30:00 →
  2026-09-22T20:30:00`. This is the backend's own documented format and needs no
  contract change. Quirk 2 is recorded as `B2.2b`.
* **Why a backend line was needed:** frontend :5173 and backend :8000 are
  different origins in the standard stack (`VITE_API_URL`). Browsers hide every
  non-safelisted response header from a cross-origin `fetch` unless the server
  lists it in `Access-Control-Expose-Headers`. Without it, the backlog's
  acceptance criterion "the filename from the RFC-6266 header is honoured" could
  not be met, so the contract was insufficient. `CORSMiddleware` got
  `expose_headers=["Content-Disposition"]`. That exposes one harmless header to
  the already-allowed origins; the allowed-origin list is unchanged.
* **Download handling (R7):** a new `requestFile()` next to `request()` in
  `api.ts`, not a bare `<a href>` (that would carry no bearer token) and no direct
  `fetch` in a component. To keep one implementation of token handling and error
  normalisation, `request()`'s token and error code was extracted into
  `authHeaders()`, `parseBody()` and `apiError()`, which both functions use. The
  change is behaviour-preserving: the F5.5 (35/35) and F5.6 (40/40) browser suites
  and `api_smoke.py` re-ran green through it.
* **Filename:** `filenameFrom()` prefers the UTF-8 `filename*` (RFC 6266 §4.3),
  falls back to `filename`, then to a local `sande-orders.csv`-style name.
  Chromium's download sanitiser turns the Persian ZWNJ (U+200C) into `_`
  (`سفارش_های-…`), so the name is saved with a plain space instead
  (`سفارش های-ساندِه-….csv`).
* **Security (R9):** every export needs the bearer token; the backend
  `StaffOrders` guard is the authority. The controls render only on
  `/admin/orders` and `/admin/products`, whose tabs the admin shell grants to
  `super_admin` / `admin` / `order_manager`, exactly the `orders` capability set.
  So support and customers never see them, and a direct URL shows the permission
  notice with zero export requests. A forced 403 renders «نقش شما اجازهٔ دریافت
  خروجی را ندارد.».
* **Repeat (R10):** exports are read-only GETs. The panel still allows one
  download at a time (both buttons disabled while one runs), so a double click
  cannot start two heavy queries.
* **Money (R11):** the report only displays backend figures (`revenue`, `units`);
  the frontend sums nothing. Column labels state the backend's rules (orders
  count = all orders; revenue and best-sellers exclude cancelled).
* **Blast radius:** `request()` is used by every API method (verified by the full
  regression above). The new `api` members and types are additive. The
  `admin.orders.tsx` empty state now renders below the panel. The
  `admin.products.tsx` header got `flex-wrap` so the three buttons wrap on mobile.

## What was done

1. **Backend** `app/main.py` — `expose_headers=["Content-Disposition"]` on the CORS
   middleware; new `tests/test_cors_expose.py`:
   * the allowed origin sees `Content-Disposition` in expose-headers;
   * a foreign origin gets no `Access-Control-Allow-Origin`.
   The positive test fails without the change (mutation-checked).
2. **`src/lib/api.ts`** — `authHeaders` / `parseBody` / `apiError` extracted from
   `request()`; `requestFile()` + `DownloadedFile` + `filenameFrom()`;
   `ExportFormat`, `ExportRange`, `SalesReport` types; `exportRange()`;
   `api.adminExportOrders(format, range, status)`,
   `api.adminExportProducts(format)`, `api.adminSalesReport(range)`.
3. **`src/components/admin/ExportControls.tsx`** (new):
   * `ExportButtons` — «خروجی CSV» / «خروجی Excel»; the running button says «در حال
     آماده‌سازی…» and both are disabled; the blob is saved via an object URL
     (revoked after 30 s); success toast; Persian inline error mapped from the
     status (401 session / 403 role / 422 range / other + network → generic),
     cleared by the next attempt.
   * `OrdersExportPanel` — «از تاریخ» / «تا تاریخ» (default: the last 30 days,
     today included, the backend's own default), «وضعیت سفارش» (همه + the five
     Rule-4 statuses). Inline validation: from after to, or a missing date,
     disables export with a Persian message. Also a Jalali "بازه: … تا … (هر دو
     روز شامل)" line and a collapsible «گزارش فروش همین بازه».
   * `SalesReportView` — fetched only when opened. It shows best-sellers (name,
     units, revenue) and daily rows (Jalali date of the UTC bucket, orders, revenue),
     plus Gregorian month totals when the range spans more than one month. Has
     loading, empty and error states.
   * `ProductsExportButtons` — catalog CSV/Excel (the endpoint takes no filters).
4. **Pages** — the panel is on `/admin/orders` (list and empty state); the buttons
   are in the `/admin/products` header.

## Files changed

* `backend/app/main.py`, `backend/tests/test_cors_expose.py` (new)
* `vogue-vintage-vibes/src/lib/api.ts`
* `vogue-vintage-vibes/src/components/admin/ExportControls.tsx` (new)
* `vogue-vintage-vibes/src/routes/_authenticated/admin.orders.tsx`
* `vogue-vintage-vibes/src/routes/_authenticated/admin.products.tsx`
* `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/backend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`, `plan/feature-roadmap.md`
* `backend/README.md`, `vogue-vintage-vibes/FEATURES.md`,
  `vogue-vintage-vibes/DESIGN_SYSTEM.md`
* this audit

## Tests / verification (all executed in this session)

| Check | Result |
| --- | --- |
| `pytest -q tests/test_cors_expose.py` | 2 passed (positive test fails with the change stashed) |
| backend `pytest -q` against the live DB | 72 passed |
| `ruff check app tests` | clean |
| `tests/api_smoke.py` | 196 checks, 0 failed |
| `bunx tsc --noEmit` | clean |
| `bun run lint` | 0 errors, 15 pre-existing warnings (none in touched files) |
| `prettier --check` on touched files | clean |
| `bun run build` | OK |
| Headless Chromium, `timezoneId: Asia/Tehran`, real download events | **45 checks, 0 failed** (run twice) |
| F5.5 / F5.6 browser suites (regression through the refactored `request()`) | 35/35, 40/40 |

The browser script:

* **Authority:**
  * anonymous → 401, customer → 403, support → 403, order_manager → 200;
  * the backend exposes `Content-Disposition` to `http://localhost:5173`.
* **Guards:**
  * anonymous `/admin/orders` → `/auth?redirect=…`;
  * customer and support on `/admin/orders` and `/admin/products` → permission
    notice, no export buttons, zero `/admin/export/*` requests;
  * order_manager downloads the orders CSV.
* **Orders CSV:**
  * default range is exactly the last 30 local days;
  * the request carries `Authorization: Bearer …`;
  * bounds are `2026-08-23T20:30:00 → 2026-09-22T20:30:00` (Tehran midnights,
    `to` = the day after);
  * saved as `سفارش های-ساندِه-YYYYMMDD-HHMM.csv`;
  * the body has the same header and row count as a direct API call for the same
    window (8 orders), and today's orders are present (inclusive end date);
  * success toast.
* **Filters and formats:**
  * `status=pending` is sent and every row in the file is `pending`;
  * Excel → `.xlsx` with the `PK` zip signature;
  * an empty window (Jan 2020) → header-only CSV.
* **Loading and repeat:** with a 1.5 s delayed route, the button reads «در حال
  آماده‌سازی…», both buttons are disabled, and a forced second click adds no
  request (1 request total).
* **Validation:** from after to → Persian error and disabled buttons; a cleared date
  → prompt and disabled buttons; no request in either case.
* **Errors:**
  * mocked 403 / 422 / 500 → the three Persian messages;
  * aborted connection → generic message;
  * the next successful download clears the alert.
* **Report:**
  * same bounds as the file export;
  * best-seller rows (3) and daily rows (1) equal the backend JSON for the same
    window, with Persian digits;
  * empty state for Jan 2020;
  * mocked 500 → error.
* **Products:**
  * CSV saved as `محصولات-ساندِه-YYYYMMDD-HHMM.csv` with 20 rows = direct API;
  * Excel `.xlsx` + `PK`;
  * with `Content-Disposition` stripped, the fallback name `sande-products.csv`
    is used.
* **Other:** no page errors; 375 px on both pages (orders with the report open) →
  no horizontal scroll.

The first run had 44/45: the Chromium ZWNJ → `_` substitution described above.
After the fix, both runs were 45/45.

## Verification level

**browser tested** (+ unit test for the CORS change, full backend suite, smoke and
lint/type/build). No clean-environment run: the backend change is one middleware
argument in `main.py` (not Docker, initdb, DDL, seeds, env configuration or startup
ordering, so Rule 14 does not apply). The running backend picked it up through its
`--reload` bind mount, confirmed with `curl` and the browser.

## What is NOT done / open

* **New `B2.2b` (discovered as `NEW-ABFE02-1`, P3, backend):**
  * `parse_range` should honour a supplied UTC offset (`astimezone(UTC)` instead
    of `replace(tzinfo=UTC)`). The UI already sends naive UTC, so it is not
    affected.
  * The CSV exports have no UTF-8 BOM, so Excel may garble the Persian text when
    the `.csv` is double-clicked. The Excel button is the safe path today.
  * The 422 detail for a bad date is English.
* Native date inputs are Gregorian; a Jalali picker would need a dependency
  decision.
* The report's daily/monthly buckets are UTC days / Gregorian months (backend
  grouping). The UI labels them as such rather than re-bucketing, because the
  frontend must not compute money aggregates.
* Filters are component state, not URL state (same as the sibling lists).
* No automated frontend test harness in the repo; the Playwright script is not
  committed.
* Not touched: AB-FE-05 (products pagination — the only other `admin.products.tsx`
  change pending, so the file collision is now cleared), F4.3, F5.9, F5.10, and the
  pre-existing `rose/emerald` classes in `admin.refunds.tsx` / `admin.index.tsx`.
* Docs untouched on purpose: `infra/README.md` (no infra change),
  `vogue-vintage-vibes/README.md` (does not list admin screens), the spec.
