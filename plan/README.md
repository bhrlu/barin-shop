# Plan — SÂNDÉ Project (frontend + backend)

> Repo-root [`../AGENTS.md`](../AGENTS.md) carries the always-loaded version of
> these rules for agents.

**Every task starts by reading the development spec** —
[`../design/SANDE_FULL_DEV_SPEC.md`](../design/SANDE_FULL_DEV_SPEC.md) (Rule 0).
Where its stack section (Supabase / Lovable Cloud) contradicts this repo, the live
FastAPI architecture wins.

This folder tracks all planned work for both halves of the project:

```
plan/
├── README.md            ← this file
├── RULES.md             ← working rules (spec-preflight + audit + doc-sync)
├── session-log.md       ← what was done / not done per session
├── backend-tasks.md     ← task list for backend/
├── frontend-tasks.md    ← task list for vogue-vintage-vibes/
├── ADMIN-BACKEND_TASKS.md   ← admin back-office split (from the dev spec)
├── ADMIN-FRONTEND_TASKS.md  ← admin back-office split (from the dev spec)
├── feature-roadmap.md   ← English feature list + prioritized todo checklist
└── audit/               ← one explanation file per completed task
    ├── 2026-09-19-backend-scaffold.md
    ├── 2026-09-19-infra-docker-stack.md
    ├── 2026-09-19-sole-backend-no-supabase.md
    ├── 2026-09-19-docker-stack-up-and-runtime-fixes.md
    ├── 2026-09-19-seed-and-frontend-switch.md
    ├── 2026-09-19-e2e-flow-docker.md
    ├── 2026-09-20-catalog-backend-and-address-fix.md
    ├── 2026-09-20-agent-doc-rule.md
    ├── 2026-09-20-frontend-f30-api-client.md
    ├── 2026-09-20-frontend-catalog-type-bridge.md
    ├── 2026-09-20-frontend-f31-search.md
    ├── 2026-09-20-backend-search-tags.md
    ├── 2026-09-20-frontend-f32-product-page.md
    ├── 2026-09-20-frontend-f33-shop-filters-compare.md
    ├── 2026-09-20-frontend-f34-recently-viewed.md
    ├── 2026-09-21-frontend-f35-f36-cart-stock-admin.md
    ├── 2026-09-21-backend-b411-b412-availability-multifacet.md
    ├── 2026-09-21-rule-spec-preflight.md
    ├── 2026-09-21-design-system-spec-merge.md
    ├── 2026-09-21-backend-frontend-nonadmin-contacts-addresses-payments.md
    ├── 2026-09-21-frontend-f27b-edit-address.md
    ├── 2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md
    ├── 2026-09-21-backend-b53-refund-bank-tracking.md
    ├── 2026-09-21-b52-f26-kpi-endpoint-dashboard-charts.md
    ├── 2026-09-21-backend-b51-audit-log.md
    ├── 2026-09-21-backend-b54-granular-staff-roles.md
    ├── 2026-09-21-frontend-f42-admin-shell-role-gating.md
    ├── 2026-09-21-frontend-f44-order-drawer-invoice-printing.md
    ├── 2026-09-21-b61-state-machine-f45-coupons-manager.md
    ├── 2026-09-21-b51a-audit-ip-f41-status-badges.md
    ├── 2026-09-22-f25-pagination-everywhere.md
    ├── 2026-09-22-b22-reports-exports.md
    ├── 2026-09-22-b24-co-purchase-recommendations.md
    ├── 2026-09-22-f25-pagination-everywhere.md
    ├── 2026-09-22-full-stack-audit-and-fixes.md
    ├── 2026-09-22-mock-dataset-seed.md
    ├── 2026-09-22-agent-guardrail-rules.md
    ├── 2026-09-22-full-backlog-audit.md
    ├── 2026-09-22-b68-variant-stock-restore.md
    ├── 2026-09-22-b69-refund-exception-handling.md
    ├── 2026-09-22-abbe03-coupon-max-discount-cap.md
    ├── 2026-09-22-f55-audit-log-viewer.md
    ├── 2026-09-22-f56-role-management-ui.md
    ├── 2026-09-22-abfe02-admin-export-controls.md
    └── 2026-09-22-abfe05-admin-products-pagination.md
```

The two `ADMIN-*.md` files hold the back-office task split (epics [BE-01]… and
[FE-01]… from the dev spec). Storefront/customer work stays in
`backend-tasks.md` / `frontend-tasks.md`; a task that belongs to the back-office
belongs in the `ADMIN-*` pair.

Legend used across the task files: `[ ]` todo · `[~]` in progress · `[x]` done
(audit link required). The user's spec lives outside this folder, in
[`../design/`](../design/).

## The rules (short version)

- **Rule 0 — Read the dev spec first.** Before any task, read
  `design/SANDE_FULL_DEV_SPEC.md`, follow it where it applies, let the live repo
  win on conflict, and record the spec check in the audit. Do not edit the spec.
- **Rule 1 — Audit after every task.** Write
  `plan/audit/YYYY-MM-DD-<task-slug>.md` covering: what the task was, the spec
  check, what changed (files), how to verify it, and what is still open, then tick
  the task checkbox with a link.
- **Rule 2 — Task lists are the source of truth.** Pick from
  `backend-tasks.md` / `frontend-tasks.md`; add new work as a checkbox first.
- **Rule 3 — Session log.** Append a section to `session-log.md` each session.
- **Rule 4 — Don't break the running store.** No changes to existing status
  strings or the cart money rules without an explicit decision.
- **Rule 5 — Update every affected doc at the end of each task.** Tick the task
  file, update `session-log.md`, the READMEs / `FEATURES.md` /
  `feature-roadmap.md` / `DESIGN_SYSTEM.md` as applicable. Stale docs are a bug.

Rules 0–5 above govern **documents**. Rules 6–15 govern **code** and apply to any
change touching code, SQL, Docker or seeds (markdown-only tasks are exempt):

- **Rule 6 — Reconnaissance before modification.** Trace module, data flow, API
  contract, auth dependency, tests, docs and existing pattern; grep every
  consumer before touching anything shared.
- **Rule 7 — Use the canonical implementation.** Reuse or fix in place; never add
  a second auth/role/pricing/API helper.
- **Rule 8 — Contract first** for every change crossing the frontend/backend
  boundary; keep response shapes backwards-compatible.
- **Rule 9 — Security boundary before the happy path.** Backend authorization is
  authoritative; test every actor including direct URL entry.
- **Rule 10 — Statuses are state machines** and repeated operations must be safe.
- **Rule 11 — Money and inventory are invariants**, computed server-side and
  covered by a test.
- **Rule 12 — Minimal diff.** No drive-by refactors; unrelated findings become
  checkboxes.
- **Rule 13 — Verify the behaviour you changed**, narrow to wide, error paths
  included; never weaken validation to go green.
- **Rule 14 — Clean-environment verification** for infra/DB/seed/config changes.
- **Rule 15 — Document what actually happened**; tick `[x]` only when verified,
  and state the honest verification level.

Full details in [RULES.md](./RULES.md).
