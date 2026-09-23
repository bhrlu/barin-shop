# Audit — F4.3 Reusable AdminDataTable (2026-09-23)

## Task

`F4.3` (P2, Batch F; decision **D8**). D8 makes `@tanstack/react-table` the one
admin table. The table state is controlled: search, filter and sort state is
explicit, pagination is server-side where the backend supports it, and bulk actions
go through the canonical API mutations. No second table abstraction.

Required:

- search, filter chips, sorting;
- server pagination;
- bulk selection and bulk actions;
- copy helpers;
- a shared toolbar;
- consistent loading / empty / error states.

Export controls stay independent (AB-FE-02). Verification: use the table on several
real admin screens. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

**Followed** from `[FE-02]`:

- `@tanstack/react-table` v8;
- `bg-muted/30` header and dual-arrow sort indicators;
- a toolbar with live search and multi-select filter chips;
- a dark floating bulk-action bar for batch status updates;
- server-side pagination, sorting and filtering;
- one-click copy for tracking codes and phones.

Also `[FE-05]`: the orders screen keeps its detail drawer. `B1`: Persian, RTL, tone
tokens.

**Deliberately different:**

- **Export is not inside the toolbar.** It stays in `OrdersExportPanel` above the
  table, as F4.3/AB-FE-02 require. The table has a `toolbarEnd` slot if a screen wants
  it there.
- **The stack header** (Supabase), as always.

## Recon / contract (Rules 6–10)

**Existing lists.** `admin.orders.tsx` was a card list:

- inline status and payment selects;
- `TrackingCodeInput` in every card;
- «کپی آدرس» and the drawer;
- `Pager`.

It showed `address["receiver"]`, which checkout never writes (it stores
`full_name`), so **customer names were blank**. `admin.users.tsx` was a flat list
with the F5.6 roles dialog.

**Backend.** `/admin/orders` and `/admin/users` supported `page`/`page_size` only.
Client-side search would have filtered one page and pretended to search everything,
so both gained **additive, optional** query parameters:

| Endpoint | Parameter | Values / rule |
| --- | --- | --- |
| `/admin/orders` | `status` | repeatable or comma-separated; validated against the five order statuses, otherwise 422 |
| `/admin/orders` | `payment_status` | validated, otherwise 422 |
| `/admin/orders` | `q` | order number, `full_name` / `receiver`, phone, customer email, tracking code |
| `/admin/orders` | `sort` | `new \| old \| total_desc \| total_asc` (`Literal`, otherwise 422) |
| `/admin/users` | `q` | email, name, phone |
| `/admin/users` | `role` | `staff \| customer` (staff = any of the four staff roles) |
| `/admin/users` | `sort` | `new \| spent \| orders` |

- **Default answer unchanged.** Without the parameters the response is the same:
  envelope or bare list, newest first.
- **Safe search.** `q` is bound as a parameter and LIKE wildcards are escaped, so
  `%` and `_` match literally. The sort keys come from whitelisted maps and are
  never interpolated from input.
- **Auth unchanged:** `StaffOrders` / `StaffUsers`.

**Bulk status (R10).** One `PATCH /orders/{id}` per selected order: the same
canonical endpoint the row select uses, so `order_lifecycle`'s state machine still
refuses an illegal move per order. The bar reports how many moved and why the others
did not. The selection **resets on any page, search, filter or sort change**, so a
bulk action never reaches rows the admin cannot see.

**Dependency.** `@tanstack/react-table@^8.21.3` (D8). The lockfile diff is +5 lines
(the new entries only). `bun add` also rewrote eight existing entries' registry URL
field; that was reverted by hand, and `bun install --frozen-lockfile` reports no
changes (R12).

## What was done

- **Backend (`routers/admin.py`):**
  - the parameters above;
  - `_like()` escaping and the whitelisted sort maps;
  - `split_multi` reused for `status` (R7).
- **`components/admin/AdminDataTable.tsx` (new):**
  - generic `AdminDataTable<T>` with manual sorting, pagination and filtering;
  - debounced `SearchBox` that follows outside resets;
  - `Chips` (multi or single, with a «همه» chip);
  - sortable headers only for accessor columns, with `aria-sort`;
  - row selection (Radix checkboxes; "select all" is page-scoped with an
    indeterminate state) feeding a floating dark bulk bar;
  - `CopyValue`;
  - skeleton rows, empty message, and an error row with «تلاش دوباره»;
  - `Pager`;
  - the scroll container is `relative`.
  - Row selection is **component-local** (ephemeral UI state). Everything the query
    depends on is controlled by the screen.
- **`routes/_authenticated/admin.orders.tsx`:**
  - the table, with the receiver read from `full_name` (fallback `receiver`, then
    «—»);
  - columns:
    - order number and phone: copyable;
    - address: copy button;
    - date and total: sortable;
    - status / payment: the existing inline selects;
    - tracking code: copyable;
    - «مشاهده و پردازش» opens the drawer.
  - the export panel above it (unchanged);
  - `toLatinDigits` on the search, so Persian digits find order numbers and phones.
  - Removed: the per-card `TrackingCodeInput` (the drawer's tracking editor, F2.8,
    remains) and the per-card item list (shown in the drawer).
  - Row-update errors now show the server message.
- **`routes/_authenticated/admin.users.tsx`:**
  - the table, with email and phone copyable;
  - role chips (staff / customers);
  - sort by joined date, orders or spend (the server sorts descending only, so a
    header click picks the column);
  - the roles dialog is unchanged.
- **`src/lib/api.ts`:** `adminOrders` / `adminUsers` take an options object, with
  types `AdminOrderListParams` / `AdminUserListParams`. The audit page's bare
  `adminUsers()` still works.
- **`src/lib/format.ts`:** `toLatinDigits`, moved here from `lib/product-form.ts`,
  which now imports it (R7).

## Files changed

- `backend/app/routers/admin.py`
- `backend/tests/test_admin_list_filters.py` (new, 12 tests)
- `backend/tests/api_smoke.py` (+3 checks)
- `vogue-vintage-vibes/package.json`, `vogue-vintage-vibes/bun.lock`
- `vogue-vintage-vibes/src/components/admin/AdminDataTable.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/admin.orders.tsx`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.users.tsx`
- `vogue-vintage-vibes/src/lib/api.ts`, `src/lib/format.ts`, `src/lib/product-form.ts`
- docs:
  - `backend/README.md` (admin list filters);
  - `vogue-vintage-vibes/FEATURES.md` (۴.۴, ۴.۵, ۶.۱۴);
  - `vogue-vintage-vibes/DESIGN_SYSTEM.md` (deps row, component row, FE-02 row, the
    stale spec-files row, notes);
  - this audit;
  - `plan/MASTER-BACKLOG.md`, `plan/frontend-tasks.md`, `plan/session-log.md`,
    `plan/README.md`.

## How to verify

**Backend.** `pytest tests/test_admin_list_filters.py`: 12 passed, each on its own
tagged customer and orders.

- Without parameters the answer is unchanged.
- Search by name, phone, email, order number and tracking code.
- LIKE wildcards are literal.
- Status: single, comma-separated and repeated; payment status.
- Every sort, checked for exact order.
- 422 on a bad status, payment status or sort.
- Users: `q` by email, phone and name; `role` staff / customer; `sort` spent and
  orders; bad role → 422.

**Negative control:** `HEAD`'s `admin.py` fails 11 of 12 (only "unchanged without
parameters" passes).

Full gates:

- `ruff` clean;
- `pytest -q` **242 passed**;
- smoke **241/0**, including the new checks: filtered envelope with ascending totals,
  seeded staff via `role=staff&q=`, `status=lost` → 422.

**Browser** (Playwright, Docker stack, admin, clipboard permission): **26 checks,
0 failed**. Setup: a fresh customer with three orders, one cancelled.

- **Orders:**
  - the table and its sortable headers render;
  - a debounced search sends one request per pause and returns the 3 orders, with
    receiver names shown;
  - status chips (`cancelled` → 1; plus `pending` → 3); the payment chip → empty
    state;
  - sort by total in both directions, with rows in order and one `aria-sort`;
  - copying the order number and phone puts them on the clipboard.
- **Bulk:**
  - select-all → «۲ مورد انتخاب شده»;
  - «در حال پردازش» → both orders `processing` on the server, then a toast and the
    bar clears;
  - an **illegal move** (processing → delivered) → the server's refusal is reported
    and nothing is delivered;
  - a filter change clears the selection.
- **Other orders behaviour:**
  - the inline selects remain and the drawer opens;
  - a forced 500 (every attempt, after React Query's retries) → «خواندن فهرست انجام
    نشد» → «تلاش دوباره» recovers;
  - 390 px: no page overflow.
- **Users:** search by email → 1; «کارکنان» → staff rows only; sort by spend →
  `sort=spent` with a descending indicator; the roles button is present.
- No page errors.

**Mutation control:** without the selection reset, "changing a filter clears the
selection" fails.

**Regression.** The F5.12 network script waited for `main main li` on `/admin/orders`.
It now waits for the table caption; that is a test-only change. It passes 27/27, and
the AB-FE-01 topbar suite (which visits `/admin/orders` for all three staff roles)
passes 70/70.

**Real bugs found by the browser run and fixed:**

1. Sortable columns need an accessor; `id` + `cell` rendered no sort buttons.
2. The unpositioned scroll container let the `sr-only` caption and Radix's hidden
   checkbox inputs widen the page to 1134 px at 390 px. It is now `relative`.

Gates (frontend container):

- `prettier`, `tsc` clean;
- `bun run lint` 0 errors / 14 warnings (unchanged);
- `bun run build` OK.

**Verification level:** integration tested (backend) + browser tested.

## What is NOT done / open

- **Other admin lists** (payments, contact messages, reviews, audit, refunds) are
  not converted yet. They keep their own lists; each needs the same optional backend
  parameters first. No task was added: F4.3's scope was the abstraction plus "multiple
  real screens".
- **Bulk status is sequential.** One PATCH per order, with no batch endpoint. That
  is fine at page size 20.
- `infra/README.md`, `feature-roadmap.md`: untouched.
