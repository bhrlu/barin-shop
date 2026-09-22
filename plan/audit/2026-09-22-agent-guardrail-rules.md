# Audit — 2026-09-22 — Agent guardrail rules (Rules 6–15)

## Task

Ad-hoc user request: **no feature work.** Inspect the existing agent instructions
(`AGENTS.md`, `plan/RULES.md`) and strengthen them so weaker coding agents make
fewer architectural, security, regression and verification mistakes. Explicit
constraints from the user: do not modify application code, tests or the design
spec, and do not mark any feature/task as completed.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before the work started.

**Followed**

- Section B1 (global invariants) and B5 (pre-flight checklist) informed the UI
  clauses of the new Rule 13 (loading/empty/error, mobile/desktop, direct URL)
  and the direct-URL admin-guard clause of Rule 9.
- Section B2 directory conventions and the `[FE-01]`…`[FE-08]` / `[BE-01]`…
  `[BE-09]` module vocabulary are used verbatim in Rule 6's data-flow trace and
  Rule 7's canonical-implementation table.
- `[BE-05]` (state machine + stock restoration) and `[BE-04]` (RBAC) are the
  direct sources of Rules 10 and 9.

**Deliberately not followed**

- The spec's stack header (Lovable Cloud / Supabase SDK / `createServerFn`).
  Per Rule 0.2 the live FastAPI + `src/lib/api.ts` architecture wins; the new
  rules name `src/lib/api.ts` as the only data layer and explicitly forbid a
  direct `fetch` to the backend. The spec itself was **not** edited.
- Part C backlog statuses are stale in several rows (refunds UI, coupons
  manager and the order drawer have shipped). Nothing was ticked in this task
  per the user's instruction, so this remains open (see below).

## What was done

`plan/RULES.md` was reorganised into two parts without altering Rules 0–5:

- **Part A — Process rules (0–5)**: unchanged text, now labelled as governing
  *documents*.
- **Part B — Engineering rules (6–15)**: new, governing *how to reason before
  changing code*. A scope note exempts markdown-only tasks, and a global stop
  condition says: if a listed question cannot be answered from the repository,
  stop and inspect rather than guess.

New rules, each traced to a defect the 2026-09-22 full-stack audit found while
Rules 0–5 were already in force:

| Rule | Prevents / detects |
| --- | --- |
| 6 — Reconnaissance before modification (+ blast radius) | editing the first plausible file; the duplicated `_optional_admin` dependency; unnoticed consumers of a changed shape |
| 7 — One canonical implementation (table of canonical homes) | the authenticated `GET /products` 500 (a stale duplicate of `get_optional_user`); duplicate auth/role/price helpers |
| 8 — Contract first across the boundary | coupon normalisation diverging between validate and redemption; pagination envelope mismatches; gratuitous response-shape changes |
| 9 — Security boundary before happy path | ungated payment simulator; unscoped `POST /payments/verify`; stale-JWT staff privileges; admin direct-URL authorization gap |
| 10 — Statuses are state machines; repeats must be safe | missing order state machine (`cancelled` → `shipped`); double-settled refund; repeated cancel inflating stock |
| 11 — Money and inventory are invariants (+ mandatory test) | stock never restored on cancellation; client-side totals; coupon usage-limit bypass |
| 12 — Minimal diff | regression risk from drive-by refactors; silent scope expansion |
| 13 — Verify what you changed, narrow to wide (+ error paths) | "tests passed" without running the suite; frontend lint failure; happy-path-only verification; weakening validation to go green |
| 14 — Clean-environment verification | the `db-init` failure on a clean `docker compose up` (seeds not calling `startup_ddl()`); "works on my existing database" |
| 15 — Document what actually happened | premature `[x]`; audits claiming a stronger verification level than performed |

`AGENTS.md` gained one concise always-loaded section (**"Mandatory: think before
you edit (Rules 6–15)"**) — one short bullet per rule plus the stop condition,
pointing at `plan/RULES.md` for the detail. The detailed text is **not**
duplicated there. `plan/README.md`'s short-rule list was extended to match.

Redundancy deliberately removed while merging the user's proposed guardrails:
"search for consumers before changing shared behavior" folded into Rule 6 as the
blast-radius clause; "when uncertain, stop and inspect" promoted to a single
Part B stop condition instead of a standalone rule; "idempotency and replay"
merged into Rule 10 (same reasoning step); "direct URL / direct API testing"
merged into Rule 9 as the multi-actor testing clause; "do not trust green tests
from a dirty environment" merged into Rule 14; "do not fix symptoms by weakening
validation", "do not create a fake test" and "error-path testing" merged into
Rule 13; "do not modify documentation mechanically" and "implemented vs
verified" merged into Rule 15, which extends Rules 1 and 5 rather than repeating
them.

## Files changed

- `plan/RULES.md` — Part A/B framing + new Rules 6–15.
- `AGENTS.md` — new concise Rules 6–15 section.
- `plan/audit/2026-09-22-agent-guardrail-rules.md` — this file.
- `plan/session-log.md` — session entry.
- `plan/README.md` — short-rule list extended with Rules 6–15.

No application code, tests, infra files or the design spec were touched.

## How to verify

```
git diff --stat            # only the five markdown files above
grep -n "Rule 1[0-5]" plan/RULES.md
grep -n "Rules 6–15" AGENTS.md plan/README.md
```

Cross-check by reading `AGENTS.md` and `plan/RULES.md` end to end: every bullet
in the AGENTS.md section maps to exactly one rule in `plan/RULES.md` Part B, and
Rule 4's protected status strings (`paid/unpaid`,
`pending/processing/shipped/delivered/cancelled`, `succeeded/failed`, `SND-…`)
and money rules (۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰ tomans) are restated, not
altered, by Rules 10 and 11.

Verification level: **documentation review only.** No test suite, lint run,
Docker stack or browser pass applies to a markdown-only change, and none is
claimed.

## What is NOT done / open

- No task checkbox was ticked and no feature marked complete (user instruction).
- The commands quoted inside Rules 13 and 14 were **not** executed in this
  session; they are copied from `AGENTS.md`, `infra/docker-compose.yml` and the
  2026-09-22 full-stack audit, which did run them.
- The Part C backlog statuses in `design/SANDE_FULL_DEV_SPEC.md` are stale for
  the refunds UI, coupons manager and order drawer. The spec is the user's
  document (Rule 0.4) and was left untouched; reconciling the plan docs is
  follow-up work.
- No new checkbox was added to `plan/backend-tasks.md` /
  `plan/frontend-tasks.md`: this task changed no product behaviour and
  discovered no new implementation work.
- `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
  `FEATURES.md`, `feature-roadmap.md` and `DESIGN_SYSTEM.md` were deliberately
  left untouched — no endpoint, script, stack, feature or UI convention changed.
