# AGENTS.md — SÂNDÉ working agreement

Applies to any agent/assistant working in this repository. The detailed rules
live in [`plan/RULES.md`](./plan/RULES.md); this file is the always-loaded
summary. **Follow these before considering any task finished.**

## Mandatory: update the docs when the task ends

An audit file alone is not enough — **after every task, update every affected
markdown file.** Stale docs are a bug. Walk this checklist:

1. **`plan/audit/YYYY-MM-DD-<task-slug>.md`** — create it (new file every task).
   It must state: the task, what was done, **files changed**, **how to verify**,
   and **what is NOT done / open**.
2. **`plan/backend-tasks.md` / `plan/frontend-tasks.md`** — tick the task `[x]`
   and add the audit link next to it. Add newly discovered work as a checkbox.
3. **`plan/session-log.md`** — append a session section: what was done, what was
   explicitly not done, and decisions taken.
4. **`backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`** —
   update when endpoints, setup steps, the stack, or scripts change.
5. **`vogue-vintage-vibes/FEATURES.md` and `plan/feature-roadmap.md`** — update
   feature status when a capability is added or removed.
6. **`vogue-vintage-vibes/DESIGN_SYSTEM.md`** — update when components, tokens,
   or UI conventions change.
7. **`plan/README.md`** — keep the folder index accurate.

If you deliberately leave a doc untouched, say so in the audit under
**What is NOT done / open**.

## Other standing rules

- **Task lists are the source of truth** — pick work from
  `plan/backend-tasks.md` / `plan/frontend-tasks.md`; add new work as a checkbox
  first. Don't delete tasks — strike them through with a reason.
- **Don't break the running store** — never change existing status strings
  (`paid/unpaid`, `pending/processing/shipped/delivered/cancelled`,
  `succeeded/failed`, `SND-…`) or the cart money rules (۸۹٬۰۰۰ shipping, free
  ≥ ۲٬۰۰۰٬۰۰۰ tomans) without an explicit user decision.
- **Architecture:** `vogue-vintage-vibes/` (TanStack Start) talks only to
  `backend/` (FastAPI) — the sole backend. No Supabase. Data layer is
  `src/lib/api.ts`.
- **Verify before finishing:** `cd backend && ./.venv/bin/python -m pytest -q`,
  `./.venv/bin/python -m ruff check app tests`, and for API changes
  `./.venv/bin/python tests/api_smoke.py` against a running stack.
- **Commits:** conventional-commit style (`fix(backend): …`, `docs(plan): …`).
  Never rewrite pushed history (Lovable syncs the branch).
