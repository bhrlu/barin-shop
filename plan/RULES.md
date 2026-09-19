# Working Rules

## Rule 1 — Audit after every task (mandatory)

After the end of **each task** (any checkbox in `backend-tasks.md` or
`frontend-tasks.md`, or any ad-hoc user request that changes code):

1. Create a file: `plan/audit/YYYY-MM-DD-<short-task-name>.md`
   (`YYYY-MM-DD` = date the task finished, e.g. `2026-09-19-checkout-wiring.md`)
2. The file MUST explain:
   - **Task** — what was requested / which task ID
   - **What was done** — actual changes, in plain language
   - **Files changed** — list of paths
   - **How to verify** — exact commands or manual steps to confirm it works
   - **What is NOT done / open** — known gaps, follow-ups
3. Mark the task checkbox `[x]` in the corresponding task file and add the
   audit file link next to it.

No task counts as finished until its audit file exists.

## Rule 2 — Task lists are the source of truth

- Pick tasks from `backend-tasks.md` / `frontend-tasks.md` first.
- New work → add it as a new checkbox in the right file before starting it.
- Don't delete tasks; strike them through (`~~task~~`) if they become irrelevant,
  with a one-line reason.

## Rule 3 — Session log

At the end of every working session, append a section to `session-log.md`:
date, what was done, what was explicitly NOT done, and decisions taken
(with the user's choices if any).

## Rule 4 — Don't break the running store

The Supabase schema and existing frontend flows are production behavior.
Backend additions must not change existing status strings
(`paid/unpaid`, `pending/processing/shipped/delivered/cancelled`,
`succeeded/failed`, `SND-…` references) or the cart money rules
(۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰ tomans) without an explicit user decision.

## Rule 5 — Update every affected doc at the end of each task

An audit file alone is not enough. **Before a task is considered finished, update
the other markdown that the change touches** — stale docs are treated as a bug.
Walk this checklist and update (or consciously skip) each file:

1. `plan/audit/YYYY-MM-DD-<slug>.md` — **new file** (Rule 1).
2. `plan/backend-tasks.md` / `plan/frontend-tasks.md` — tick the task and add the
   audit link; add any newly discovered task as a checkbox.
3. `plan/session-log.md` — append the session section (Rule 3).
4. `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md` —
   update when endpoints, setup steps, the stack, or scripts change.
5. `vogue-vintage-vibes/FEATURES.md` and `plan/feature-roadmap.md` — update
   feature status (✅/`[x]`/`[ ]`) when a capability is added or removed.
6. `vogue-vintage-vibes/DESIGN_SYSTEM.md` — update when components, tokens, or
   UI conventions change.
7. `plan/README.md` — keep the folder index/legend accurate.

If a change makes a doc wrong, fix it in the same task. If you deliberately leave
one untouched, say so in the audit file under **What is NOT done / open**.
