# Audit — 2026-09-25 · Rules 0–5 always apply (semantic correction)

## Task

Small docs-only correction to the selective rule-loading workflow (`39af476`):
the rule-topic map's rows (e.g. F5.19 → `0, 6, 6a, 7, 8, 9, 12, 13, 15`) could
be read as omitting Rules 1–5 for code tasks. Canonical semantics: **Part A
(Rules 0–5) applies to every task; the map selects only Part B (6–15).**

## Spec check (Rule 0)

- Section-scoped check: this is a documentation/workflow correction; no B3
  module, B0/B1 UI rule or B5 checklist item applies. Spec untouched.
- Followed: Rule 0, Rules 1–5. Part B code rules not applicable (markdown-only).
- Deliberately ignored: none.

## What was done

- `plan/CONTEXT-MAP.md` — map retitled "(Rules 0–5 always; this table selects
  Part B)", statement "**Rules 0–5 apply to every task**" added, table column
  renamed to "applicable Part B rules (6–15)", docs row now "none (Rules 0–5
  only)". No rule text duplicated; table same size.
- `.agents/skills/task-scoped-reconnaissance/SKILL.md` — Rule loading step 1
  now "Rules 0–5 are always applicable"; steps renumbered; "Part B rules
  (6–15)" made explicit.
- `AGENTS.md` — bootstrap step 4 and the think-before-you-edit paragraph now
  state Rules 0–5 always apply, then task-relevant Part B sections only.
- `plan/MASTER-BACKLOG.md` — §3 item 3 reworded to "always-applicable Rules
  0–5 plus the Part B (6–15) sections identified by the rule-topic map".
- No `plan/RULES.md` change; no rule renumbered; no task status changed; no
  new context file or skill.

## Files changed

- `plan/CONTEXT-MAP.md`, `.agents/skills/task-scoped-reconnaissance/SKILL.md`,
  `AGENTS.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
  `plan/audit/2026-09-25-rules-05-always-apply.md` (this file).

## How to verify

- `grep -n "Rules 0–5 apply to every task" plan/CONTEXT-MAP.md AGENTS.md` →
  both hit.
- Skill step 1 = "Rules 0–5 are always applicable."
- `git diff 39af476 -- plan/RULES.md` → empty (rule text untouched).
- `grep -c "^## Rule " plan/RULES.md` → 17 (unchanged).
- Backlog task statuses/counts untouched (`git diff 39af476 --stat` shows only
  the five workflow docs + audit + session log).

## What is NOT done / open

- Nothing else; verification level: **implemented + reviewed** (docs-only).
