# AGENTS.md — SÂNDÉ working agreement

Applies to any agent/assistant working in this repository. The detailed rules
live in [`plan/RULES.md`](./plan/RULES.md); this file is the always-loaded
summary. **Follow these before considering any task finished.**

## Session bootstrap — start narrow, expand on evidence

Default reading order at task start (no exploration before this is done):

1. `AGENTS.md` (this file) + the task request itself.
2. The task entry in [`plan/MASTER-BACKLOG.md`](./plan/MASTER-BACKLOG.md) (the
   canonical backlog; search by task ID, do not read the whole file).
3. [`plan/CONTEXT-MAP.md`](./plan/CONTEXT-MAP.md) — repo map, spec index and
   rule-topic map.
4. The relevant **spec sections** (via the spec index — not the whole spec)
   and the RULES sections: **Rules 0–5 always apply**, then only the
   task-relevant **Part B (6–15) sections** via the rule-topic map — not the
   whole `plan/RULES.md`.
5. Only the files on the task's dependency path
   (route/component → `src/lib/api.ts` → backend endpoint → service → test).
6. A prior audit **only** when it touched the same area.

Expand the search only when evidence requires it (shared code, cross-boundary
contract, authorization, a shared helper change, tests revealing a dependency,
or an explicitly cross-module task) — see Rule 6 in
[`plan/RULES.md`](./plan/RULES.md). Once you know the owner, files, contract,
auth, tests and acceptance criteria, **stop reconnaissance and implement.**

## Mandatory: check the dev spec before the task starts

Every task (backend, frontend, docs, infra), with no exceptions, is checked
against [`design/SANDE_FULL_DEV_SPEC.md`](./design/SANDE_FULL_DEV_SPEC.md)
**by section, not by full read**: locate the sections covering the task via the
spec index in [`plan/CONTEXT-MAP.md`](./plan/CONTEXT-MAP.md) (topic → section →
keywords) and read only those. Read the whole spec only when a task spans many
areas or the index cannot locate the ground. Then:

- **Follow it where it applies** — UI/UX rules (Sections B0/B1), directory
  conventions (B2), module specs (B3) and the Part C backlog are the reference for
  anything they cover (`[FE-02]` data tables, `[FE-05]` order drawer, …).
- **The live repo wins on conflict.** The spec's stack header still says Supabase /
  Lovable Cloud / `createServerFn`; this repo is FastAPI-only with its own JWT and
  `src/lib/api.ts` as the data layer. Never follow that stale stack, and never
  change a Rule-4 status string or the cart money rules to match it.
- **Report it in the audit**: which spec sections were followed, which were
  deliberately ignored, and why. A conflict is a finding, not a failure.
- **Don't edit the spec itself** unless the user asks — it is the user's document.
  If it is merely out of date, say so in the audit and fix the plan docs instead.

## Mandatory: update the docs when the task ends

An audit file alone is not enough — **after every task, update every affected
markdown file.** Stale docs are a bug. Walk this checklist:

1. **`plan/audit/YYYY-MM-DD-<task-slug>.md`** — create it (new file every task).
   It must state: the task, the **spec check** (Rule 0), what was done, **files
   changed**, **how to verify**, and **what is NOT done / open**.
2. **`plan/backend-tasks.md` / `plan/frontend-tasks.md`** — tick the task `[x]`
   and add the audit link next to it. Add newly discovered work as a checkbox.
3. **`plan/session-log.md`** — append a session section: what was done, what was
   explicitly not done, and decisions taken.
4. **`backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`** —
   update when endpoints, setup steps, the stack, or scripts change.
5. **`vogue-vintage-vibes/FEATURES.md` and `plan/feature-roadmap.md`** — update
   feature status when a capability is added or removed.
6. **`vogue-vintage-vibes/DESIGN_SYSTEM.md`** — update when components, tokens,
   or UI conventions change.
7. **`plan/README.md`** — keep the folder index accurate.

If you deliberately leave a doc untouched, say so in the audit under
**What is NOT done / open**.

## Mandatory: think before you edit (Rules 6–15)

Rules 0–5 govern **documents**; Rules 6–15 in [`plan/RULES.md`](./plan/RULES.md)
govern **code**, and exist because the 2026-09-22 full-stack audit found P0/P1
defects while Rules 0–5 were already in force. They apply to any change touching
code, SQL, Docker or seeds — a markdown-only change needs Rules 0–5 only.
**Rules 0–5 apply to every task; load only the task-relevant Part B (6–15)
sections on top**, using the rule-topic map in
[`plan/CONTEXT-MAP.md`](./plan/CONTEXT-MAP.md); the always-loaded summaries
below are part of this file, and the whole of `plan/RULES.md` is reserved for
genuinely cross-cutting work or when a required section cannot be located.

- **R6 — Recon first, task-scoped.** Before the first edit, name the owning
  module, the data flow, the API contract, the auth dependency, existing tests,
  the task/spec/audit docs, and one sibling that already solves this — gathered
  from the narrowest source that answers each. Work the smallest relevant
  dependency graph (task → route/component → `api.ts` method → backend endpoint
  → service → relevant test); expand beyond it only on evidence (shared code,
  cross-boundary contract, authz, shared helper change). Repo-wide consumer
  grep is required **only** when changing shared code. Once owner, files,
  contract, auth, tests and acceptance criteria are known, **stop
  reconnaissance and implement** (Rule 6a adds the reading discipline: search +
  line ranges over whole-file reads, no rereads, no unrelated files, no
  audit-folder browsing).
- **R7 — One canonical implementation.** Reuse (or fix in place) the existing
  helper; never add a second. Auth → `app/auth.py`; roles → `services/roles.py`;
  totals → `services/pricing.py`; transitions/stock restore →
  `services/order_lifecycle.py`; payments/refunds → `services/payments.py`;
  customer notifications (in-app + SMS/email) → `services/notifications.py`; stock
  ledger rows → `services/inventory_log.py`; all
  frontend HTTP → `src/lib/api.ts`. No direct `fetch` to the backend.
- **R8 — Contract first.** State request/response shape, status codes, error
  shape, auth + ownership, pagination (`Page<T>` vs array) and normalisation
  before editing. Don't change a shape because a cleaner one appeals.
- **R9 — Security before the happy path.** Who calls it, what they may reach,
  is it really theirs, is the mutation allowed, can a stale JWT or client-sent
  role/price/id bypass it. Roles come from `user_roles`, not the token claim.
  Hidden nav and disabled buttons are never authorization; test anonymous,
  customer, each staff role, admin, wrong-owner, and direct URL entry.
- **R10 — Statuses are state machines.** Identify allowed/terminal transitions
  and side effects first, then answer "what if this runs twice?" for payments,
  refunds, cancellation, stock, roles, callbacks and seeds.
- **R11 — Money and stock are invariants.** The backend computes authoritative
  totals; the frontend never does. Any money/stock change adds or updates a test
  in `backend/tests/`.
- **R12 — Minimal diff.** No drive-by refactors, renames, reformatting or
  dependency bumps. Unrelated findings become a new checkbox, not a new edit.
- **R13 — Verify what you changed:** targeted test → full `pytest -q` → `ruff`
  / `bun run lint` (+ `bun run build`) → `tests/api_smoke.py` → the real runtime
  path for UI/Docker changes. Cover error paths, not just the happy path. Never
  claim a suite you didn't run, never fake a test green, never weaken a
  validation to make a test pass.
- **R14 — Clean-environment proof for infra/DB/seed/config changes:**
  `docker compose down -v && docker compose up -d --build`, `db-init` exits 0
  with all four seed stages, `/health` responds. A working local DB is not
  evidence; suspect a dirty environment before blaming the code.
- **R15 — Document reality.** Tick `[x]` only when implemented **and** tested
  **and** verified against the acceptance criteria; state the honest verification
  level (implemented / locally tested / integration tested / browser tested /
  clean-environment tested / fully verified).
- **When unsure** which implementation is canonical, which transition is valid,
  which role should have access, or whether a change is breaking — stop and
  inspect the repo. Don't guess or invent architecture.

## Other standing rules

- **`design/SANDE_FULL_DEV_SPEC.md` is checked at both ends** — read before the
  task (Rule 0), recorded in the audit after it. The detailed rule lives in
  [`plan/RULES.md`](./plan/RULES.md) Rule 0 + Rule 4b.
- **Task lists are the source of truth** — pick work from
  `plan/backend-tasks.md` / `plan/frontend-tasks.md`; add new work as a checkbox
  first. Don't delete tasks — strike them through with a reason.
- **Don't break the running store** — never change existing status strings
  (`paid/unpaid`, `pending/processing/shipped/delivered/cancelled`,
  `succeeded/failed`, `SND-…`) or the cart money rules (۸۹٬۰۰۰ shipping, free
  ≥ ۲٬۰۰۰٬۰۰۰ tomans) without an explicit user decision.
- **Architecture:** `vogue-vintage-vibes/` (TanStack Start) talks only to
  `backend/` (FastAPI) — the sole backend. No Supabase. Data layer is
  `src/lib/api.ts`.
- **Verify before finishing:** `cd backend && ./.venv/bin/python -m pytest -q`,
  `./.venv/bin/python -m ruff check app tests`, and for API changes
  `./.venv/bin/python tests/api_smoke.py` against a running stack.
- **Commits:** conventional-commit style (`fix(backend): …`, `docs(plan): …`).
  Never rewrite pushed history (Lovable syncs the branch).
