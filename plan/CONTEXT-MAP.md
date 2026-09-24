# Repository context map — SÂNDÉ

> Navigation only. Read this instead of exploring the tree; open files only when
> a task touches them. Detailed rules live in [`RULES.md`](./RULES.md) (Rule 0 +
> Rule 6a govern how you use this file).

## Repo map

```text
vogue-vintage-vibes/            Frontend (TanStack Start / React)
  src/lib/api.ts                ALL frontend HTTP — the data layer (no direct fetch)
  src/lib/                      shared helpers (auth.tsx, format.ts, …)
  src/routes/                   pages; _authenticated/admin.* = admin screens
  src/components/               shared UI (incl. components/admin/AdminDataTable)

backend/                        FastAPI — the sole backend
  app/routers/                  HTTP endpoints, one module per area
  app/services/                 business logic (see canonical table)
  app/models.py                 SQLAlchemy models → PostgreSQL
  app/auth.py                   authentication + Staff* capability guards
  tests/                        pytest; api_smoke.py = live-stack smoke

infra/                          docker compose stack (db, minio, backend, worker, db-init)
design/SANDE_FULL_DEV_SPEC.md   dev spec — read by section (index below), never wholesale
plan/MASTER-BACKLOG.md          canonical execution backlog (JSON task index inside)
```

Data flow: route/component → `src/lib/api.ts` → `app/routers/*` →
`app/services/*` → `app/models.py` → PostgreSQL (MinIO for files).

## Canonical implementations (Rule 7 — never add a second)

| Concern | Canonical home |
| --- | --- |
| Auth / current user | `backend/app/auth.py` |
| Roles & capabilities | `backend/app/services/roles.py` |
| Totals / shipping / discount | `backend/app/services/pricing.py` |
| Checkout & stock decrement | `backend/app/services/checkout.py` |
| Order transitions / cancel | `backend/app/services/order_lifecycle.py` |
| Payments / refunds | `backend/app/services/payments.py` |
| Stock ledger | `backend/app/services/inventory_log.py` |
| Notifications (in-app/SMS/email) | `backend/app/services/notifications.py` |
| Pagination envelope | `backend/app/services/pagination.py` (frontend: `toPage()` in `src/lib/api.ts`) |
| Audit logging | `backend/app/services/audit.py` |
| Frontend HTTP | `src/lib/api.ts` |
| Price formatting | `src/lib/format.ts` |

Full table with constraints: `RULES.md` Rule 7.

## Tests

- `backend/tests/` — targeted pytest modules per area; run one before the suite.
- `backend/tests/api_smoke.py` — smoke against a running stack (API changes).
- Frontend: `bun run lint` (+ `bun run build` when build-affecting).

## Spec index (Rule 0 — locate, then read only those sections)

`design/SANDE_FULL_DEV_SPEC.md` sections. Line numbers drift — search by the
section label, e.g. `### [FE-02]`.

```text
topic                          -> section     -> keywords
Product variants & inventory   -> [BE-01]     -> variants, matrix, stock, inventory
Promotional engine & coupons   -> [BE-02]     -> coupon, discount, promotion
Returns & refunds              -> [BE-03]     -> refund, return request
Admin RBAC & audit logging     -> [BE-04]     -> roles, staff, audit log
Order lifecycle RPC            -> [BE-05]     -> updateOrderStatus, order status
Coupon validation engine       -> [BE-06]     -> validateCoupon, coupon limits
SMS gateway                    -> [BE-07]     -> SMS, Kavenegar, notifications
Orders & financial export      -> [BE-08]     -> exportOrders, CSV, XLSX
Dashboard aggregations         -> [BE-09]     -> getDashboardKPIs, KPI
Public/webhook endpoints       -> Epic A3     -> webhook, callback
Visual direction & palette     -> B0.1–B0.5   -> colors, typography, spacing, design tokens
Global rules & invariants      -> B1          -> RTL, Persian, invariants, a11y
Directory layout & routing     -> B2          -> routes, folder naming, conventions
Admin shell & sidebar          -> [FE-01]     -> sidebar, AdminLayout, navigation
Admin data table               -> [FE-02]     -> table, pagination, filters, bulk actions
KPI dashboard                  -> [FE-03]     -> dashboard, charts, KPIs
Product & SKU management       -> [FE-04]     -> product editor, SKU, variants
Orders & detail drawer         -> [FE-05]     -> order drawer, OrderDetailSheet, invoice
Refund & returns center        -> [FE-06]     -> refunds UI, returns
Coupon manager                 -> [FE-07]     -> coupons UI, campaigns
Customer 360 / CRM             -> [FE-08]     -> customer profile, users admin
Reusable code blocks           -> B4.1–B4.3   -> formatPrice, status badge, skeletons
Pre-flight checklist           -> B5          -> verification checklist
Feature backlog                -> Part C      -> prioritized platform features
```

Read the whole spec only when a task spans many of these areas or creates new
ground the index cannot locate.
