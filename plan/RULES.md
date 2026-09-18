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
