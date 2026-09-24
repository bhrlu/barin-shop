---
name: task-scoped-reconnaissance
description: Bootstrap a SÂNDÉ task with minimal context — locate the task entry, spec sections and target files without reading the whole repo, spec or audit history. Load when starting any task.
---

# Task-scoped reconnaissance

Goal: know the **smallest relevant dependency graph**, then implement.

## Bootstrap (read in this order, nothing more)

1. `AGENTS.md` + the task request itself.
2. The task entry in `plan/MASTER-BACKLOG.md` — search by task ID, never read
   the whole file.
3. `plan/CONTEXT-MAP.md` — repo map + spec index.
4. The relevant **spec sections** of `design/SANDE_FULL_DEV_SPEC.md` via the
   index (topic → section → keywords). Never read the whole spec unless the task
   spans many areas or the index cannot locate the ground.
5. Only the files on the task's dependency path:
   `route/component → src/lib/api.ts → backend endpoint → service → relevant test`.
6. A prior audit **only** if it touched the same area — read that one audit,
   never the audit folder.

## Rule loading

1. Rules 0–5 are always applicable.
2. Identify the task category (docs, UI, backend API, money/stock, DB/infra,
   …).
3. Consult the rule-topic map in `plan/CONTEXT-MAP.md`.
4. Load only the applicable Part B rules (6–15) listed for that category —
   never the whole file by default.
5. Add more Part B rules only when the task expands into another concern.

## Targeted search

- Search for symbols/patterns with line numbers, then read a line range — not
  whole files.
- One sibling example that already solves the same shape is enough.
- One test file covering the behaviour is enough.

## Progressive expansion (only on evidence)

Go beyond the task graph only when: the target code is shared, the API contract
crosses frontend/backend, authorization is involved, a shared helper changes,
tests/types reveal another dependency, or the task is explicitly cross-module.
Expand one hop at a time. A change to shared code requires a repo-wide
consumer `grep` before editing (Rule 6 blast radius) — localized tasks skip it.

## Stop condition (mandatory)

You know: owning module · relevant files · API contract · auth requirement ·
relevant tests · acceptance criteria. **Stop reconnaissance. Start
implementing.** Do not reread inspected files, open unrelated task files, or
scan "for completeness".

## Context efficiency

- Search + line ranges over whole-file reads; large files are read in windows.
- No rereads of files already held in context this task.
- No historical audits, unrelated backlog entries, or tree-walking for
  localized tasks.
- Docs-only tasks never trigger code verification (RULES.md Part B scope).
