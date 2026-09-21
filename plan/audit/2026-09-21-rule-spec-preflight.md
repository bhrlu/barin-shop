# Audit — new Rule 0: check `design/SANDE_FULL_DEV_SPEC.md` before every task — 2026-09-21

**Task (user request):** add a rule that `SANDE_FULL_DEV_SPEC.md` must be checked
**before starting each task**. Two decisions were taken with the user:

1. **Authority — "read first, current stack wins"**: the spec is read before every
   task and followed where it applies; where it conflicts with the live
   architecture (FastAPI as the sole backend, no Supabase) or an existing decision,
   the repo wins and the deviation is reported in the audit.
2. **Scope — every task, no exceptions** (backend, frontend, docs, infra), with the
   audit stating which spec sections were touched or deliberately ignored.

**Spec check (Rule 0.3):** this task changed rules and docs only, so the UI/API
sections do not apply — **B0/B0.1–B0.5 (design tokens, spacing, toasts)**, **B1
(global invariants)**, **B2 (directory layout)**, **B3/[FE-01…FE-08]** and **Part C**
were read and deliberately not acted on (no UI, no route and no endpoint change).
What *did* apply is the spec's **stack header**: it still declares Lovable Cloud /
Supabase and `createServerFn`, which contradicts this repo (FastAPI-only,
`src/lib/api.ts`, own JWT). That conflict is exactly what the new precedence clause
(Rule 0.2) resolves; **the spec file itself was left unmodified** (Rule 0.4).

---

## What was done

1. **`AGENTS.md` (always-loaded)** — new section *«Mandatory: read the dev spec
   before the task starts»* placed directly above the existing end-of-task doc
   checklist, so the pre-task and post-task obligations read as a pair: follow the
   spec where it applies, let the live repo win on conflict, report the spec check
   in the audit, don't edit the spec. The audit-file requirement now lists the
   **spec check** among its mandatory contents, and the standing-rules list links
   to the detailed rule.
2. **`plan/RULES.md`** — the detailed version:
   - **New Rule 0** with four numbered obligations (follow where it applies, live
     repo wins, report in the audit, reconcile-but-don't-edit).
   - **Rule 1** now requires a **Spec check** bullet in every audit.
   - **New Rule 4b** ties the two ends together: the spec is checked when the task
     opens (Rule 0) and closed (Rule 5) — a task with no spec line in its audit is
     not finished, exactly like a task with no audit.
   - **Rule 5** checklist item 1 mentions the spec check.
   - **Rule 4 wording fix**: it began «The Supabase schema and existing frontend
     flows are production behavior», which stopped being true when Supabase was
     removed. It now says the current DB schema, storefront flows and API contracts
     are the protected behaviour — the rule's actual content (status strings, cart
     money rules) is unchanged.
3. **`plan/README.md`** — the folder index now points at
   `../design/SANDE_FULL_DEV_SPEC.md` at the top, lists it as the user's document
   outside `plan/`, and the "rules (short version)" leads with Rule 0.

---

## Files changed

| File | Change |
|---|---|
| `AGENTS.md` | new pre-task spec section; audit contents + standing-rules entries |
| `plan/RULES.md` | new Rule 0, Rule 4b; Rule 1 gains the Spec check bullet; Rule 4 stale-Supabase wording fixed |
| `plan/README.md` | spec indexed with its precedence pointer; Rule 0 in the short rules |
| `plan/audit/2026-09-21-rule-spec-preflight.md` | **this file** |
| `plan/session-log.md` | Session 16 |

`design/SANDE_FULL_DEV_SPEC.md` was **not** modified (Rule 0.4) and the task lists
were **not** touched — a process rule is not backend or frontend work, so it gets
no checkbox in `backend-tasks.md` / `frontend-tasks.md` (recorded here per Rule 5's
"say so in the audit"). `backend/README.md`, `infra/README.md`,
`vogue-vintage-vibes/README.md`, `FEATURES.md`, `feature-roadmap.md` and
`DESIGN_SYSTEM.md` are unaffected: no endpoint, feature, component, setup step or
script changed.

---

## How to verify

```sh
grep -n "SANDE_FULL_DEV_SPEC" AGENTS.md plan/RULES.md plan/README.md
grep -n "Rule 0\|Rule 4b\|Spec check" plan/RULES.md AGENTS.md
grep -n "Supabase" plan/RULES.md      # only the Rule 0.2 conflict note remains
git status --porcelain                # design/SANDE_FULL_DEV_SPEC.md must be absent
```

Read the four places in order to check the intent survives the summary/expansion
split: `AGENTS.md` (short, always loaded) → `plan/RULES.md` Rule 0 (detailed) →
Rule 4b (both ends) → `plan/README.md` (index + precedence pointer). Then confirm
the spec file itself is untouched in `git status` (it is untracked, so it appears as
`?? design/` — the check is that its mtime/content did not change this session).

---

## What is NOT done / open

- **The spec is not reconciled with the repo.** Its stack header (Supabase, Lovable
  Cloud, `createServerFn`), its `src/components/admin/AdminLayout.tsx` /
  `AdminDataTable.tsx` / `OrderDetailSheet.tsx` / `RefundActionDialog.tsx` /
  `admin.refunds.tsx` / `admin.coupons.tsx` targets, its `@tanstack/react-table` +
  RHF/Zod tooling and its `formatPrice` / `toPersianDigits` helper names all differ
  from what exists (`formatToman` / `toFa`; a tab-shell admin, not a sidebar shell).
  Part C statuses are stale too (reviews and the variant matrix are largely shipped,
  listed as *Pending*). Rule 0.3 makes each future audit responsible for naming the
  conflicts it hits; a one-off reconciliation pass into `feature-roadmap.md` /
  `frontend-tasks.md` (and optionally a "current status" header inside the spec)
  would be worth doing — **not done here**, because it is a user-facing document
  change the user did not ask for.
- **No checkbox in the task lists** for this rule (see *Files changed*).
- **No automated check** enforces the rule — it is convention plus review, like the
  audit rule itself. Nothing stops a task from skipping the read; the audit line is
  the only paper trail.
- **Rule 0.2 lists two superseding sources** (the running architecture and decisions
  in `feature-roadmap.md`). If a decision is ever recorded only in a session log or
  an audit, a future agent may not find it — worth folding decisions into
  `feature-roadmap.md` as they are taken.
