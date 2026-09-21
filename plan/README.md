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
    └── 2026-09-21-frontend-f21b-f24-f28-admin-inbox-refunds-tracking.md
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

Full details in [RULES.md](./RULES.md).
