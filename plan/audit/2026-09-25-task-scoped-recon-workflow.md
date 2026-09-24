# Audit — 2026-09-25 · Task-scoped agent reconnaissance workflow

## Task

Change the **agent workflow** (docs/rules only) so sessions bootstrap with
task-scoped reconnaissance instead of reading the whole dev spec, backlog,
audits and source tree. Not an application change.

## Spec check (Rule 0)

- Checked **by section** against `design/SANDE_FULL_DEV_SPEC.md` (the new
  section-scoped Rule 0). Relevant: B1/B2 (docs conventions, directory layout),
  B5 (verification checklist — not applicable, docs-only). The spec file itself
  is untouched per Rule 0.4 (user's document); the topic→section→keywords index
  was extracted into `plan/CONTEXT-MAP.md` instead of copying spec content.
- Followed: Rule 0 (section-scoped check), Rules 1–5 (audit, backlog pointer,
  session log, doc updates), Rule 12 (minimal diff).
- Deliberately ignored: none.

## What was done

1. **`plan/CONTEXT-MAP.md`** (new, ~120 lines) — navigation-only repo map
   (frontend/backend/infra/tests), canonical-implementation table (Rule 7
   summary; full table stays in RULES.md), and the spec index
   (topic → spec section → keywords, ~25 entries). No architecture prose.
2. **`plan/RULES.md`** — Rule 0 reworded to **section-scoped** spec checking via
   the index (intent preserved: check before every task, follow/live-repo-wins/
   report clauses untouched); Rule 6 made **task-scoped** (smallest dependency
   graph, evidence-gated expansion, mandatory stop rule, blast-radius grep
   required only for shared code); new **Rule 6a — reading discipline** (7
   concise rules: search + line ranges, no whole-file reads for one symbol, no
   rereads, audits only same-area, no unrelated task files, no tree-walking,
   stop when known). Rules 1–5, 7–15 untouched.
3. **`AGENTS.md`** — added "Session bootstrap" section (default reading order +
   expand-on-evidence + stop rule); replaced the mandatory full-spec-read
   paragraph with section-scoped checking (Rule 0 still exists and is still
   mandatory); R6 summary bullet updated to match. No other section changed.
4. **`plan/MASTER-BACKLOG.md`** — §3 "Agent execution contract" bootstrap list
   replaced with the task-scoped order (task entry by ID, spec by section,
   inspect only the task's dependency path, Rule 6 stop rule). The "before
   marking DONE" checklist is untouched.
5. **`.agents/skills/task-scoped-reconnaissance/SKILL.md`** (new, ~50 lines) —
   on-demand skill: bootstrap order, targeted search, progressive expansion,
   stop condition, context efficiency. Not auto-loaded; adds no session context
   unless invoked.
6. **`plan/README.md`** — added `CONTEXT-MAP.md` to the plan-folder index.
7. **`plan/session-log.md`** — session entry appended.
8. **Task tracking** — this work was not a backlog checkbox (agent-workflow
   change), so no task file was ticked and MASTER-BACKLOG task statuses were
   not touched. Next backlog pointer `F5.19` unchanged.

## Files changed

- `AGENTS.md` (edited)
- `plan/RULES.md` (edited)
- `plan/CONTEXT-MAP.md` (new)
- `plan/MASTER-BACKLOG.md` (edited, §3 only)
- `plan/README.md` (edited, folder index)
- `plan/session-log.md` (appended)
- `plan/audit/2026-09-25-task-scoped-recon-workflow.md` (new)
- `.agents/skills/task-scoped-reconnaissance/SKILL.md` (new)

## How to verify

- `AGENTS.md`: "Session bootstrap" section present; spec paragraph says "by
  section, not by full read"; R6 bullet says "task-scoped"; no other section
  altered.
- `plan/RULES.md`: Rule 0 title "Check the dev spec before starting"; Rule 6
  title "Task-scoped reconnaissance"; Rule 6a exists with 7 numbered rules;
  Rules 7–15 unchanged; no security/auth/verification requirement removed.
- `plan/CONTEXT-MAP.md`: ≤150 lines, no duplicated spec text.
- `plan/MASTER-BACKLOG.md`: §3 bootstrap references `plan/CONTEXT-MAP.md` and
  the Rule 6 stop rule; task JSON statuses unchanged.
- Internal links resolve (`plan/CONTEXT-MAP.md`, `plan/RULES.md`,
  `plan/MASTER-BACKLOG.md`, audit path).
- F5.19 walkthrough: from `AGENTS.md` → backlog entry (search "F5.19") →
  context map → spec section `[BE-01]`/admin data-table guidance →
  `admin.inventory.tsx` → `src/lib/api.ts` inventory method →
  `services/inventory_log.py` → `backend/tests/` ledger tests. No full-file
  reads of routes/services/audits required.

## What is NOT done / open

- No application code, backend behaviour, API contract, schema or dependency
  changed; no tests were run (docs-only task — RULES.md Part B does not apply).
- Skill support is runtime-level (on-demand `skill` load), not repo-configured
  tooling; the skill file is a convention that works because the runtime can
  load it, but no hook auto-invokes it.
- `design/SANDE_FULL_DEV_SPEC.md` untouched by design (Rule 0.4).
- Verification level: **implemented + reviewed** (docs-only; nothing to run).
