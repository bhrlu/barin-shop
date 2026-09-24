# Audit — 2026-09-25 · D10: browser E2E (Playwright) deferred by decision

## Task

Record the user's decision that real browser automation is planned but
**deferred**, without installing anything or changing the application/test
setup. Documentation/rule-only.

## Spec check (Rule 0)

- Section-scoped: docs/workflow change; no B3 module, B0/B1 UI rule or B5
  checklist item applies. The spec was not edited.
- Followed: Rule 0, Rules 1–5, Rule 12 (minimal diff). Part B not applicable
  (markdown-only).
- Deliberately ignored: none.

## What was done

1. **`plan/MASTER-BACKLOG.md`** — new resolved decision **D10 — Browser E2E
   (Playwright): deferred** in §4, with the activation gate
   `PLAYWRIGHT_E2E_STATUS = DEFERRED` (only an explicit user instruction such
   as **`ACTIVATE PLAYWRIGHT`** sets it to ACTIVE), the while-deferred
   prohibitions (no installs, no `package.json`/`bun.lock` edits for
   Playwright, no configs/specs, no recon into browser tooling, no changing
   F5.19 just to satisfy browser verification), and the honesty rule (never
   claim `browser tested` without a real browser runtime; record the
   strongest truthful level and leave browser verification OPEN). The JSON
   `execution_policy` gains `"playwright_e2e_status": "DEFERRED"` so the gate
   is machine-readable next to `agent_start_task`. §4's preamble notes D10 is
   canonical policy recorded as deferred.
2. **`AGENTS.md`** — one bullet in the always-loaded invariants: gate name,
   pointer to D10, the honesty rule and the activation phrase. Four lines;
   no Playwright instructions are loaded and no recon is required before
   activation.
3. **`plan/audit/2026-09-25-f519-admin-inventory-ledger-viewer.md`** — the
   F5.19 "browser click-through OPEN" item now references D10 (status and
   verification level unchanged).
4. **`plan/README.md`** — the plan-folder index line for `MASTER-BACKLOG.md`
   now mentions "resolved decisions (incl. D10: Playwright deferred)" for
   discoverability.
5. **`plan/session-log.md`** — session entry appended.

Nothing else changed: no application code, no dependency files, no Playwright
package/config/spec, no workflow redesign, no historical audit rewritten, no
task status changed (F5.19 stays DONE with `integration tested + build
verified`, browser OPEN).

## Files changed

- `AGENTS.md` (one invariant bullet)
- `plan/MASTER-BACKLOG.md` (D10 + execution_policy flag)
- `plan/README.md` (index line)
- `plan/audit/2026-09-25-f519-admin-inventory-ledger-viewer.md` (D10 reference)
- `plan/audit/2026-09-25-d10-playwright-deferred.md` (this file)
- `plan/session-log.md` (appended)

## How to verify

- `git diff <previous-commit> --stat` shows only the six files above (docs).
- `grep -n "playwright" package.json bun.lock` (in `vogue-vintage-vibes/`) →
  no matches; no `playwright.config.*` anywhere; no `*.spec.ts` E2E files.
- `grep -n "PLAYWRIGHT_E2E_STATUS" AGENTS.md plan/MASTER-BACKLOG.md` → gate
  present in both; `grep -n '"playwright_e2e_status"' plan/MASTER-BACKLOG.md`
  → `"DEFERRED"`.
- Discoverability: the gate is visible in the always-loaded `AGENTS.md`, in
  the canonical backlog's machine-readable policy, and via `plan/README.md`.

## What is NOT done / open

- Playwright infrastructure itself — deliberately not started; it activates
  only on the user's explicit `ACTIVATE PLAYWRIGHT` (then per Rules 13/15).
- Verification level: **implemented + reviewed** (docs-only; nothing to run).
