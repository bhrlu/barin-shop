# Audit — 2026-09-21 — B5.2 KPI endpoint + F2.6 admin dashboard charts

## Task

**B5.2** (`backend-tasks.md`) and **F2.6** (`frontend-tasks.md`), implemented as
one unit because F2.6 was explicitly blocked on B5.2: the KPI aggregation
endpoint (`GET /admin/kpis?range=`) from spec **[BE-09]**, and the admin
dashboard that consumes it (KPI cards with deltas, revenue area chart, order
status donut, urgent-actions callout) from spec **[FE-03]**.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before starting ([BE-09] and [FE-03]
re-verified against the implementation).

- **Followed:**
  - [BE-09] signature — `timeRange: 'today' | '7d' | '30d' | 'all'` (here
    `range=`) returning **Gross Revenue, Net Revenue, Total Paid Orders, AOV,
    Pending Refunds Count, Low-Stock Alert Count**. Plus the two series
    [FE-03] needs: daily revenue points and the order-status breakdown.
  - [FE-03] layout — four KPI cards in a bento grid with MoM delta badges
    (green up / red down), weekly-window sales **area chart** with
    terracotta→transparent gradient and Persian tooltip, order-status **donut**
    with inline color legend, and an amber **urgent actions** callout linking
    to the pending refunds and low-stock screens. Recharts styled through CSS
    variables of the design tokens (`--terracotta`, `--sage`, `--gold`,
    `--clay`), TanStack Query caching.
- **Deliberately ignored / adapted:**
  - The spec's `getDashboardKPIs` **RPC / createServerFn** shape — this repo's
    data layer is FastAPI + `src/lib/api.ts` (Rule 0.2); the endpoint is a plain
    admin route.
  - Low-stock threshold — spec says «< 5 units»; the repo has a per-product
    `low_stock_threshold` (default 5), so the count uses each product's own
    threshold (a superset of the spec's rule).
  - «فروش امروز» card label — the card shows **net revenue for the selected
    range** («فروش خالص») rather than hardcoding today, because the page now has
    a range selector (a superset of the spec's fixed cards).
  - Donut chart spec colours (paid/processing/shipped/cancelled) — mapped onto
    the repo's semantic tokens via a status→token table instead of raw palette
    classes (B1.1 no hardcoded colors).
  - `recharts` was installed-but-unused; the repo wins on the stack header and
    this task finally uses it (F2.6's whole point).

## What was done

**Backend (`GET /admin/kpis`, B5.2):**

- `_KPI_RANGES` whitelist maps `today|7d|30d|all` to interval strings; unknown
  range → 422 with a Persian message.
- Gross/net revenue, paid orders and AOV for the window, **plus deltas**
  against the preceding window of equal length (`all` → deltas `null`).
- `pendingRefunds` (status `pending`/`approved` — i.e. actionable) and
  `lowStock` (active products at/below their own threshold) are store-wide.
- `series`: one `generate_series` point per day in the window (30 points for
  `all`), revenue counted only for paid, non-cancelled orders. The interval
  literal is inlined from the whitelist — asyncpg refuses to CAST a text
  *parameter* to interval (found and fixed during live verification).
- `statusBreakdown`: order counts per status inside the window.
- Smoke: block-shape + 8-point `7d` series assertions, all ranges, bogus 422,
  unauthenticated call.

**Frontend (`/admin` rewrite, F2.6):**

- `api.ts`: `KpiRange`, `AdminKpis` types + `api.adminKpis(range)`.
- `admin.index.tsx` rewritten: range selector (امروز/۷ روز/۳۰ روز/همه), four
  KPI cards with `DeltaBadge`, amber urgent-actions callout with links to
  `/admin/refunds` and `/admin/inventory`, `recharts` AreaChart (LTR-wrapped
  container, Persian tooltip) and Pie donut with legend, skeletons while
  loading, and the previous latest-orders list preserved (separate
  `adminStats` query so the KPI endpoint stays cache-friendly).
- The old plain stat cards (درآمد کل/سفارش‌ها/…) are replaced by the ranged
  KPI block; `adminStats` itself is unchanged and still feeds latest orders.

## Files changed

- `backend/app/routers/admin.py`
- `backend/tests/api_smoke.py`
- `vogue-vintage-vibes/src/lib/api.ts`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.index.tsx`
- Docs: `plan/backend-tasks.md`, `plan/frontend-tasks.md`, `plan/README.md`,
  `plan/session-log.md`, `backend/README.md`,
  `vogue-vintage-vibes/DESIGN_SYSTEM.md`, this audit.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q           # 39 passed
./.venv/bin/python -m ruff check app tests              # clean
./.venv/bin/python tests/api_smoke.py                   # 138 checks, 0 failed
# live spot-check (admin token):
#   GET /admin/kpis?range=7d → 8 series points, deltas block
#   GET /admin/kpis?range=bogus → 422 «بازه نامعتبر است»
```

```bash
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit   # clean
bun run build                                                # passes (recharts bundled)
```

Manual: open `/admin` as an admin — range chips switch the KPI cards; the
revenue area chart shows the daily trend; the donut shows the status
distribution with legend; with a pending refund or low stock present, the amber
«اقدامات فوری» callout links to the right screens.

## What is NOT done / open

- `recharts` default export style (composite components) pulls the whole
  library into the admin chunk; tree-shaking/lazy-loading the admin routes is
  untouched perf work, not part of this task.
- The KPI cards' watermark icons and the MoM **month-over-month** semantics:
  deltas compare the selected window with the preceding window (e.g. 7d vs the
  previous 7d), not calendar months — deliberate, it matches the range selector.
- F4.x chrome (sidebar shell, data grid) untouched; the dashboard sits in the
  existing tab shell.
- Docs updated in the same task (see list). `FEATURES.md` untouched: the
  dashboard upgrade is a spec-alignment improvement, not a gap closure (gap
  ۶.۱۲ «گزارش‌ها/نمودار ندارد» refers to sales *reports* (B2.2), which remain
  open — noted here so the roadmap doesn't read as two different pieces).
