# Audit — 2026-09-25 · Thin always-loaded AGENTS.md

## Task

Surgical docs-only optimization: `AGENTS.md` (always loaded every session)
duplicated the detailed R6–R15 summaries, the R7 canonical-path list, the R13
command sequences and the Rule-5 doc checklist that live canonically in
`plan/RULES.md` / `plan/CONTEXT-MAP.md`. Rewrite it as a small operating
contract without weakening any rule. Preserves the selective-loading system of
`a72f93e`, `39af476`, `53cb99b`.

## Spec check (Rule 0)

- Section-scoped: docs/workflow change; no B3/B0/B1/B5 spec item applies; spec
  untouched. Followed Rules 0–5; Part B not applicable (markdown-only).
- Deliberately ignored: none.

## What was done

`AGENTS.md` rewritten in place (157 → 80 lines, 9,860 → 4,170 chars):

- **Kept** — session bootstrap (task entry → context map → spec sections +
  Rules 0–5 + selected Part B → dependency path → same-area audit), the
  Rule-0 section-scoped spec check, non-negotiable global invariants
  (FastAPI-only / no Supabase-RLS-RPC, no second API client / canonical
  implementations, backend authorization authoritative, frozen status strings
  + money rules, never fake tests / weaken validation, never invent
  architecture, commit style), doc-completion duties (audit, task sync,
  session log, affected docs, Rule 4b two-ends check), and a one-line-per-rule
  index of R6–6a–R15 as a compact reference.
- **Removed (category-4 duplication only)** — the 9 detailed R6–R15 bullet
  summaries, the R7 canonical-implementation path list (CONTEXT-MAP canonical
  table is the map for it), the 7-item affected-docs checklist (Rule 5), the
  R13/R14 command sequences (RULES.md Rule 13/14), and the "Other standing
  rules" block whose content was folded into the invariants/finish sections.
- No new context file, no new skill; the R6–R15 one-liners point to RULES.md
  as canonical; nothing was moved to another document.

## Files changed

- `AGENTS.md` (rewritten in place)
- `plan/audit/2026-09-25-thin-agents-md.md` (this file)
- `plan/session-log.md` (appended)

## How to verify

- `wc -l AGENTS.md` → 80 (before: 157; −77 lines / ~49%).
- `git diff 53cb99b -- plan/RULES.md plan/CONTEXT-MAP.md` → empty (both
  byte-for-byte unchanged).
- Bootstrap still names Rules 0–5 as always-applicable and Part B as selected
  via the context map; invariants section lists all seven required reminders;
  links (`plan/RULES.md`, `plan/CONTEXT-MAP.md`, `plan/MASTER-BACKLOG.md`,
  `design/SANDE_FULL_DEV_SPEC.md`) resolve.
- No application file changed; no task status changed.

## What is NOT done / open

- Nothing else; verification level: **implemented + reviewed** (docs-only;
  nothing to run).
