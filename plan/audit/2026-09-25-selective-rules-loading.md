# Audit — 2026-09-25 · Selective RULES loading (context optimization follow-up)

## Task

Complete the agent context optimization started in `a72f93e`: stop loading the
entire `plan/RULES.md` (~430 lines) on every task and load only the rules
relevant to the task type. Workflow/docs change only — no application code.

## Spec check (Rule 0)

- Checked **by section** (as Rule 0 now requires): B5's verification checklist
  does not apply to a docs-only change; no B3 module or B0/B1 UI rule is
  touched. No spec text was copied or edited (Rule 0.4 respected).
- Followed: Rule 0 (section-scoped), Rules 1–5 (audit, session log, doc-sync,
  minimal diff). Part B code rules correctly not applied (markdown-only task);
  no verification work was manufactured.
- Deliberately ignored: none.

## What was done

1. **`plan/CONTEXT-MAP.md`** — added a **rule-topic map**
   (task type → RULES section numbers, ~12 rows; e.g. docs → 0–5, admin UI →
   0, 6, 6a, 7, 8, 9, 12, 13, 15, money/stock → +10, 11, DB/infra → +14,
   cross-cutting → 0–15). Rule numbers only; no rule text duplicated
   (no second source of truth). Kept under 150 lines total.
2. **`AGENTS.md`** — bootstrap step 3/4 now loads **relevant spec sections
   AND relevant RULES sections** (both via the context map); replaced the
   remaining "Read the full text in `plan/RULES.md` before a non-trivial code
   change" with "Load only the RULES sections relevant to the current task…
   whole file reserved for genuinely cross-cutting work or when a required
   section cannot be located."
3. **`plan/RULES.md`** — added only a short "How to load this file" note under
   the title (canonical source, selective loading, all rules remain
   authoritative, whole-file reading reserved). **Rules 0–15 untouched: no
   deletions, no renumbering, no wording changes to any rule.**
4. **`plan/MASTER-BACKLOG.md`** — §3 item 3 changed from "Read
   `plan/RULES.md`" to "Read the applicable `plan/RULES.md` sections identified
   by the rule-topic map in `plan/CONTEXT-MAP.md` — not the entire file unless
   the task spans multiple rule areas." Task definitions/statuses untouched.
5. **`.agents/skills/task-scoped-reconnaissance/SKILL.md`** — added a small
   "Rule loading" section (identify category → consult context map → load only
   those sections → expand only on new concerns). Still ~65 lines total.

## Files changed

- `AGENTS.md` (edited)
- `plan/RULES.md` (edited — header note only)
- `plan/CONTEXT-MAP.md` (edited — rule-topic map added)
- `plan/MASTER-BACKLOG.md` (edited — §3 bootstrap wording only)
- `.agents/skills/task-scoped-reconnaissance/SKILL.md` (edited)
- `plan/audit/2026-09-25-selective-rules-loading.md` (new)
- `plan/session-log.md` (appended)

## How to verify

- `AGENTS.md` contains no "Read the full text in `plan/RULES.md`" instruction;
  bootstrap lists "relevant RULES sections" via the rule-topic map.
- `plan/CONTEXT-MAP.md` contains "## Rule-topic map" with rows for docs
  (0–5), admin UI, backend API, money/stock, DB/infra, cross-cutting.
- `grep -c "^## Rule " plan/RULES.md` → 17 (Rules 0–5, 4b, 6, 7–15) and
  `### Rule 6a` still present as a sub-heading — none deleted or renumbered.
- `git diff a72f93e -- plan/RULES.md` shows only the header note added.
- `plan/MASTER-BACKLOG.md` §3 references the rule-topic map and "not the
  entire file".
- The skill has a "## Rule loading" section and stays under 100 lines.
- F5.19 conceptual test: rule-topic row "admin / staff-gated UI" →
  0, 6, 6a, 7, 8, 9, 12, 13, 15 (+10/11 only if stock behaviour changes) —
  Rules 1–5's doc mechanics and 14 are not loaded.
- Docs-only task → row "docs / markdown only" → Rules 0–5 only.
- No application file changed; no backlog task status changed.

## What is NOT done / open

- No rule text moved or rewritten; `design/SANDE_FULL_DEV_SPEC.md` untouched;
  no new context document or skill created; no application code, tests, or
  dependencies touched; no test suite run (docs-only task — Part B does not
  apply).
- Verification level: **implemented + reviewed** (docs-only; nothing to run).
