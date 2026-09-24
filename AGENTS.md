# AGENTS.md — SÂNDÉ working agreement

Always-loaded operating contract. Detailed rules live canonically in
[`plan/RULES.md`](./plan/RULES.md); navigation lives in
[`plan/CONTEXT-MAP.md`](./plan/CONTEXT-MAP.md). Do not duplicate them here.

## Session bootstrap — start narrow, expand on evidence

1. `AGENTS.md` (this file) + the task request itself.
2. The task entry in [`plan/MASTER-BACKLOG.md`](./plan/MASTER-BACKLOG.md)
   (the canonical backlog; search by task ID, do not read the whole file).
3. [`plan/CONTEXT-MAP.md`](./plan/CONTEXT-MAP.md) — repo map, spec index and
   rule-topic map.
4. The relevant **spec sections** (via the spec index — not the whole spec)
   and the RULES sections: **Rules 0–5 always apply**, then only the
   task-relevant **Part B (6–15) sections** via the rule-topic map — not the
   whole `plan/RULES.md`.
5. Only the files on the task's dependency path
   (route/component → `src/lib/api.ts` → backend endpoint → service → test).
6. A prior audit **only** when it touched the same area.

Expand only on evidence (shared code, cross-boundary contract, authorization,
a shared-helper change, a test-revealed dependency, an explicitly cross-module
task). Once owner, files, contract, auth, tests and acceptance criteria are
known, **stop reconnaissance and implement** (Rule 6).

## Check the dev spec before every task (Rule 0)

Every task is checked against
[`design/SANDE_FULL_DEV_SPEC.md`](./design/SANDE_FULL_DEV_SPEC.md) **by
section, not full read**, via the spec index in CONTEXT-MAP. Follow it where
it applies; the live repo wins on stale spec stack wording; record the
followed/ignored sections in the audit; never edit the spec unless asked.
(Full text: `plan/RULES.md` Rule 0.)

## Non-negotiable global constraints

- The live repo architecture wins over stale spec stack wording: FastAPI-only
  backend with its own JWT; no Supabase / RLS / RPC / `createServerFn`.
- No second API client or parallel auth/role/pricing system: all frontend HTTP
  goes through `src/lib/api.ts`; reuse the canonical implementations (table in
  `plan/CONTEXT-MAP.md`, Rule 7).
- Backend authorization is authoritative; roles come from `user_roles`, never
  the token claim; hidden nav and disabled buttons are not authorization.
- Existing status strings (`paid/unpaid`,
  `pending/processing/shipped/delivered/cancelled`, `succeeded/failed`,
  `SND-…`) and the cart money rules (۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰
  tomans) do not change without an explicit user decision.
- Never fake a test, never claim a suite you didn't run, never weaken a
  validation to make a test pass.
- Never invent architecture when repository evidence is missing — stop and
  inspect; asking beats guessing.
- Commits: conventional-commit style (`fix(backend): …`, `docs(plan): …`);
  never rewrite pushed history.

## Engineering rules (Part B) — load selectively, follow fully

Rules 0–5 apply to every task. For code tasks, load the applicable Part B
(6–15) sections listed by the rule-topic map in `plan/CONTEXT-MAP.md`; the
whole of `plan/RULES.md` is reserved for genuinely cross-cutting work or when
a required section cannot be located. Their one-line shape:

R6 task-scoped recon with a mandatory stop rule · 6a reading discipline ·
R7 one canonical implementation · R8 contract first · R9 security before the
happy path · R10 state machines, safe repeats · R11 money/stock invariants ·
R12 minimal diff · R13 verify narrow→wide, error paths included · R14
clean-environment proof · R15 document reality.

## Finish every task (Rules 1–5)

1. Audit file `plan/audit/YYYY-MM-DD-<slug>.md` — task, spec check (Rule 0),
   what changed, how to verify, what is open.
2. Tick the task checkbox and add the audit link
   (`plan/MASTER-BACKLOG.md` / task files); new work becomes a checkbox first.
3. Append `plan/session-log.md`.
4. Update every other affected doc (the full checklist is Rule 5) — stale
   docs are a bug; deliberate skips go in the audit.

`design/SANDE_FULL_DEV_SPEC.md` is checked at both ends: Rule 0 opens the
task, the audit records the spec check (Rule 4b).
