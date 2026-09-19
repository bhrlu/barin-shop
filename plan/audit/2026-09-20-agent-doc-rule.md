# Audit — End-of-task doc-update rule + root AGENTS.md

**Date:** 2026-09-20
**Task:** User request — "add rules: after each task ends, update files."

## What was done

1. **`plan/RULES.md` — new Rule 5 “Update every affected doc at the end of each
   task.”** An audit file alone is not enough; before a task is finished, every
   affected markdown file must be updated (audit, task list, session log, the
   READMEs, `FEATURES.md` / `feature-roadmap.md`, `DESIGN_SYSTEM.md`,
   `plan/README.md`). Rules renumbered/ordered 1–5.
2. **New repo-root `AGENTS.md`** — the always-loaded, condensed version of the
   same agreement (end-of-task doc checklist + standing rules: task lists are the
   source of truth, don't break the running store, sole-backend architecture,
   verify commands, commit style).
3. **`plan/README.md`** — index and rules summary already list Rule 5.

## Files changed

- `plan/RULES.md` (Rule 5)
- `AGENTS.md` (new)
- `plan/README.md` (Rule 5 summary; root `AGENTS.md` noted)
- `plan/audit/2026-09-20-agent-doc-rule.md` (this file)

## How to verify

```bash
grep -n "Rule 5" plan/RULES.md plan/README.md
sed -n '1,40p' AGENTS.md
```

## What is NOT done / open

- No automated enforcement (e.g. a CI check that an audit file exists per
  commit) — the rule is process/convention only.
- `plan/backend-tasks.md` / `plan/frontend-tasks.md` are unchanged because this
  task added no backend/frontend work.
