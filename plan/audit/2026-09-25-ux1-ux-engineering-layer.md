# 2026-09-25 — UX-1 UX engineering layer

## Task

User task brief (2026-09-25): establish a canonical, maintainable UX
engineering layer so future frontend agents implement explicit, testable
behavior — states, async, confirmation, a11y — instead of visually plausible
UI. Explicitly a documentation/process task: no product redesign, no UI
refactor, no reopening completed features, no Playwright activation (D10
stands; the canonical phrase `ACTIVATE PLAYWRIGHT` is untouched).

## Spec check (Rule 0)

The spec's design-relevant sections were located via the CONTEXT-MAP index
(B0.1–B0.5 visual direction, B1 global invariants incl. a11y/RTL, B4.1–B4.3
reusable blocks, B5 pre-flight) — they are **visual/invariant** material and
stay with the design system; none of them defines behavioral UX rules, so no
spec section is contradicted or duplicated. Per Rule 0 the spec was **not
edited**. `DESIGN_SYSTEM.md` §5 (spec-vs-repo precedence) is untouched; the
new layer references it rather than absorbing it.

## What was done (architecture)

Verified no equivalent mechanism existed (grep: no UX docs; `DESIGN_SYSTEM.md`
is purely visual — tokens, components, stack, §8 gaps, authoring checklist),
then extended the existing architecture with exactly two new files and four
one-block integrations:

```text
AGENTS.md                        one-line invariant (no rule text)
plan/CONTEXT-MAP.md              pointer to the UX rule-topic map
plan/UX-CONTEXT-MAP.md  (new)    task-scoped selection + UX Acceptance Criteria template
plan/UX-RULES.md        (new)    canonical behavioral rules, stable section IDs
plan/MASTER-BACKLOG.md           JSON entry UX-1 (DONE), §11/§16/§19 hooks
vogue-vintage-vibes/DESIGN_SYSTEM.md   boundary note (visual ≠ behavioral)
plan/README.md                   folder index rows
plan/session-log.md, this audit
```

Selection works exactly like the Part B rule-topic map: `UX-CONTEXT-MAP.md`
maps task surfaces to section IDs; rule text lives only in `UX-RULES.md`;
`UX-CORE` is always in scope for frontend tasks; the map unions rows for
multi-surface tasks. The conditional **UX Acceptance Criteria** template makes
the contract task-scoped (a static display component lists only
Loading/Empty/Error; a destructive mutation pulls UX-CONFIRM Level 2).

## UX contexts (final IDs)

UX-CORE · UX-FORM · UX-ASYNC · UX-CONFIRM (Level 1 normal / Level 2 typed) ·
UX-DESTRUCTIVE · UX-DIALOG · UX-DRAWER · UX-TABLE · UX-SEARCH · UX-PAGINATION ·
UX-A11Y · UX-KEYBOARD · UX-RESPONSIVE · UX-NOTIFICATION · UX-PERMISSION ·
UX-DATA-FRESHNESS. Every ID is justified by an existing surface (table below);
no speculative sections were created.

## Validation against representative real code (brief §17)

Targeted reads only (grep + line windows, Rule 6a):

| Sample | Rule anchored to it |
| --- | --- |
| `RolesDialog` (`admin.users.tsx`, typed confirmation) | UX-CONFIRM Level 2: input starts empty, phrase displayed, trim+case-insensitive matching stated per component, 403-specific error copy, invalidate `admin-users` + `admin-audit-logs` |
| `AdminDataTable` (`isError` / `emptyMessage` / `aria-pressed` chips) | UX-TABLE.1 states, UX-A11Y accessible names |
| `CustomerProfileDrawer` (Sheet + `useMutation` + toast) | UX-DRAWER canonical, UX-ASYNC, UX-NOTIFICATION |
| `lib/cart.tsx` `useCartQuote` (`keepPreviousData`, focus refetch, server quote) | UX-CORE.1, UX-DATA-FRESHNESS.2/.4, UX-SEARCH.3 debounce convention (`HeaderSearch`) |
| `stock-issues.ts` (per-reason Persian copy, closed reason set) | UX-CORE.3 error copy discipline |

Two existing conventions were found and made canonical rather than invented:
the `RolesDialog` typed-confirm matching rule (trim + case-insensitive,
stated per component) and the 403-specific toast message pattern. No rule
contradicts a live pattern; nothing existing had to change.

## Known gaps (documented, NOT fixed — brief §18)

Existing UX weaknesses observed in passing (e.g. the `OrderDetailDrawer`
`exhaustive-deps` warning, drawer orders-tab pagination) are **not** addressed
here — this task changes no product code. Future tasks consume the contract;
the gaps can become backlog checkboxes if wanted.

## Verification

* JSON block in `MASTER-BACKLOG.md` parses (`python3 -c "json.load(...)"` on
  the fenced content) — 60 executable tasks, counts object consistent
  (55 done / 5 open, UX-1 included).
* Cross-references resolved: every relative link in the new/edited docs
  points at an existing file (`UX-RULES.md` ↔ `UX-CONTEXT-MAP.md` ↔
  `CONTEXT-MAP.md` ↔ `DESIGN_SYSTEM.md`; `plan/README.md` rows match `ls plan/`).
* Rule 6a respected in the docs themselves: maps list IDs, never rule text;
  no duplication between AGENTS.md / RULES.md / UX-RULES.md.
* Playwright untouched: no dependency/config/spec changes (`grep -ri playwright`
  on the diff → docs only), D10 unchanged.
* `git status` audited: only the intended files changed; no source code, no
  completed task reopened (AB-FE-06/F3.2c untouched beyond their already-
  committed state).
* Markdown-only task → no tsc/lint/pytest run (Rules 6/13 scope; nothing in
  `backend/` or `src/` changed).

## What is NOT done / open

* Browser-verifiable acceptance execution — deferred with D10; the ⟦PW⟧
  assertion markers in `UX-RULES.md` are the future mapping, written but not
  wired to any runner.
* The UX Acceptance Criteria pattern applies to **new** frontend tasks from
  now on; no retrospective retrofit of completed tasks.
* Optionally: backfill small UX-gap checkboxes (§ Known gaps) in a later
  session if the user wants them tracked.

## Docs synced

`AGENTS.md`, `plan/CONTEXT-MAP.md`, `plan/README.md`, `plan/MASTER-BACKLOG.md`
(JSON + §11 + §16 + §19), `vogue-vintage-vibes/DESIGN_SYSTEM.md`,
`plan/session-log.md`, this audit.
