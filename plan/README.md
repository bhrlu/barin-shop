# Plan — SÂNDÉ Project (frontend + backend)

> Repo-root [`../AGENTS.md`](../AGENTS.md) carries the always-loaded version of
> these rules for agents.

This folder tracks all planned work for both halves of the project:

```
plan/
├── README.md            ← this file
├── RULES.md             ← working rules (audit rule + doc-sync rule)
├── session-log.md       ← what was done / not done per session
├── backend-tasks.md     ← task list for backend/
├── frontend-tasks.md    ← task list for vogue-vintage-vibes/
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
    └── 2026-09-20-frontend-catalog-type-bridge.md
```

Legend used across the task files: `[ ]` todo · `[~]` in progress · `[x]` done
(audit link required).

## The rules (short version)

- **Rule 1 — Audit after every task.** Write
  `plan/audit/YYYY-MM-DD-<task-slug>.md` covering: what the task was, what
  changed (files), how to verify it, and what is still open, then tick the task
  checkbox with a link.
- **Rule 2 — Task lists are the source of truth.** Pick from
  `backend-tasks.md` / `frontend-tasks.md`; add new work as a checkbox first.
- **Rule 3 — Session log.** Append a section to `session-log.md` each session.
- **Rule 4 — Don't break the running store.** No changes to existing status
  strings or the cart money rules without an explicit decision.
- **Rule 5 — Update every affected doc at the end of each task.** Tick the task
  file, update `session-log.md`, the READMEs / `FEATURES.md` /
  `feature-roadmap.md` / `DESIGN_SYSTEM.md` as applicable. Stale docs are a bug.

Full details in [RULES.md](./RULES.md).
