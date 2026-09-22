# Working Rules

Two groups of rules apply to every task in this repository:

- **Part A — Process rules (0–5)**: what to read before a task and what to write
  after it. These already existed and are unchanged.
- **Part B — Engineering rules (6–15)**: *how to reason before changing code*.
  They exist because the 2026-09-22 full-stack audit found real P0/P1 defects
  (half-seeded `db-init`, a 500 on authenticated `GET /products`, an ungated
  payment simulator, a double-settled refund, stock never restored on
  cancellation, a missing order state machine, a stale-JWT privilege hold, an
  unscoped payment verification, an admin direct-URL gap) while Rules 0–5 were
  already in force. Rules 0–5 govern documentation; Rules 6–15 govern code.

**Scope of Part B.** Rules 6–15 apply to any change that touches code,
configuration, SQL, Docker, or seeds. A change that only edits markdown under
`plan/`, `design/` or a `README.md` needs Rules 0–5 only — do not manufacture
verification work for a documentation-only task.

**Stop conditions.** If, at any point in Rules 6–15, you cannot answer a listed
question from the repository itself, stop and inspect the repository before
editing. Do not guess, do not invent architecture, and do not "standardise" on a
generic FastAPI/React convention when this repo already has an established
pattern. Asking the user is better than guessing.

# Part A — Process rules

## Rule 0 — Read the dev spec before starting (mandatory)

Before **any** task — backend, frontend, docs or infra — read
[`../design/SANDE_FULL_DEV_SPEC.md`](../design/SANDE_FULL_DEV_SPEC.md) and check
the work against it. This rule has no exceptions.

1. **Follow it where it applies.** Its UI/UX rules (Sections B0/B1), directory
   conventions (B2), module specs (B3) and the Part C backlog are the reference
   for anything they cover — an admin screen should look like `[FE-02]`/`[FE-05]`
   describe it, not like a new invention.
2. **The live repo wins on conflict.** The spec's stack header still describes
   Lovable Cloud / Supabase and `createServerFn`; this repo is **FastAPI-only**
   (`backend/` is the sole backend, `@/lib/api.ts` is the data layer) with its own
   JWT, and there is no `src/integrations/supabase/`. Where the spec contradicts
   the running architecture, a decision recorded in `feature-roadmap.md`, or a
   status string protected by Rule 4, do what the repo does — never silently
   follow the stale stack.
3. **Report it.** The audit file must name the spec sections the task followed
   and the ones it deliberately ignored or contradicted, each with a one-line
   reason. A conflict is a finding, not a failure.
4. **Reconcile when cheap.** If the spec is merely out of date (a feature it
   lists as *Pending* that already shipped), say so in the audit and fix the plan
   docs in the same task. Do **not** edit `design/SANDE_FULL_DEV_SPEC.md` itself
   unless the user asks — it is the user's document.

## Rule 1 — Audit after every task (mandatory)

After the end of **each task** (any checkbox in `backend-tasks.md` or
`frontend-tasks.md`, or any ad-hoc user request that changes code):

1. Create a file: `plan/audit/YYYY-MM-DD-<short-task-name>.md`
   (`YYYY-MM-DD` = date the task finished, e.g. `2026-09-19-checkout-wiring.md`)
2. The file MUST explain:
   - **Task** — what was requested / which task ID
   - **Spec check** — which `design/SANDE_FULL_DEV_SPEC.md` sections applied and
     which were deliberately ignored (Rule 0.3)
   - **What was done** — actual changes, in plain language
   - **Files changed** — list of paths
   - **How to verify** — exact commands or manual steps to confirm it works
   - **What is NOT done / open** — known gaps, follow-ups
3. Mark the task checkbox `[x]` in the corresponding task file and add the
   audit file link next to it.

No task counts as finished until its audit file exists.

## Rule 2 — Task lists are the source of truth

- Pick tasks from `backend-tasks.md` / `frontend-tasks.md` first.
- New work → add it as a new checkbox in the right file before starting it.
- Don't delete tasks; strike them through (`~~task~~`) if they become irrelevant,
  with a one-line reason.

## Rule 3 — Session log

At the end of every working session, append a section to `session-log.md`:
date, what was done, what was explicitly NOT done, and decisions taken
(with the user's choices if any).

## Rule 4 — Don't break the running store

The current database schema, the storefront flows and every existing API contract
are production behaviour. Backend additions must not change existing status strings
(`paid/unpaid`, `pending/processing/shipped/delivered/cancelled`,
`succeeded/failed`, `SND-…` references) or the cart money rules
(۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰ tomans) without an explicit user decision.

## Rule 4b — The spec is checked at both ends

Rule 0 opens every task (read the spec, state the conflicts) and Rule 5 closes it
(the audit records what was followed and what was ignored). A task with no spec
line in its audit is not finished, in the same way a task with no audit is not
finished.

## Rule 5 — Update every affected doc at the end of each task

An audit file alone is not enough. **Before a task is considered finished, update
the other markdown that the change touches** — stale docs are treated as a bug.
Walk this checklist and update (or consciously skip) each file:

1. `plan/audit/YYYY-MM-DD-<slug>.md` — **new file** (Rule 1), including its
   **Spec check** line (Rule 0).
2. `plan/backend-tasks.md` / `plan/frontend-tasks.md` — tick the task and add the
   audit link; add any newly discovered task as a checkbox.
3. `plan/session-log.md` — append the session section (Rule 3).
4. `backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md` —
   update when endpoints, setup steps, the stack, or scripts change.
5. `vogue-vintage-vibes/FEATURES.md` and `plan/feature-roadmap.md` — update
   feature status (✅/`[x]`/`[ ]`) when a capability is added or removed.
6. `vogue-vintage-vibes/DESIGN_SYSTEM.md` — update when components, tokens, or
   UI conventions change.
7. `plan/README.md` — keep the folder index/legend accurate.

If a change makes a doc wrong, fix it in the same task. If you deliberately leave
one untouched, say so in the audit file under **What is NOT done / open**.

# Part B — Engineering rules

## Rule 6 — Reconnaissance before modification (all code changes)

Do not edit the first file that looks relevant. Before the first edit, write down
(in your working notes, and later in the audit) the answers to all seven:

1. **Owning module** — which of `backend/app/routers/*`, `backend/app/services/*`,
   `backend/app/models.py`, `vogue-vintage-vibes/src/lib/*`,
   `vogue-vintage-vibes/src/routes/*`, `vogue-vintage-vibes/src/components/*`,
   or `infra/` actually owns this behaviour.
2. **Data flow** — trace the full path. In this repo it is almost always:
   route/component → `src/lib/api.ts` → `backend/app/routers/<x>.py` →
   `backend/app/services/<x>.py` → `backend/app/models.py` → PostgreSQL
   (and MinIO for files). A change that alters behaviour crossing any of those
   arrows must be considered at every arrow, not only where you type.
3. **API contract** — the exact endpoint(s) involved (Rule 8).
4. **Auth requirements** — which dependency in `backend/app/auth.py` guards it
   (`CurrentUser`, `AdminUser`, `OptionalUser`, `StaffOrders`, `StaffRefunds`,
   `StaffCatalog`, `StaffCoupons`, `StaffReviews`, `StaffContactInbox`,
   `StaffUsers`, `StaffStats`, `StaffAudit`, `StaffSettings`) and why that one.
5. **Existing tests** — grep `backend/tests/` for the behaviour
   (`test_pricing_and_coupons.py`, `test_availability_and_filters.py`,
   `test_variants.py`, `test_addresses.py`, `api_smoke.py`).
6. **Documents** — the task checkbox in `plan/*-tasks.md` or
   `plan/ADMIN-*_TASKS.md`, the matching spec section (Rule 0), and any prior
   `plan/audit/*.md` that touched the same area. Prior audits record decisions
   you must not silently reverse.
7. **Existing pattern** — find a sibling that already solves the same shape of
   problem (another router, another `api.ts` method, another admin route) and
   follow it.

**Blast radius.** Before changing anything shared — an API response shape, a
shared TypeScript type, a status string, a helper in `src/lib/`, a method on the
`api` object, an auth/role helper, price formatting, stock logic, or a shared
component — `grep -rn` the repository for *every* consumer, in both
`backend/` and `vogue-vintage-vibes/src/`, and list them before editing. If the
list is longer than you expected, that is a signal to make a smaller change, not
a bigger one.

## Rule 7 — Use the canonical implementation; never a second one

Never assume an existing helper is correct, and never add a parallel one because
the existing one was not immediately visible. Before writing a helper, search for
prior art and reuse it; if the existing one is wrong, **fix it in place** so all
callers benefit, rather than shadowing it.

Actively look for: duplicate FastAPI dependencies, duplicated auth/role
resolution, duplicated validation, conflicting normalisation, two sources of
truth, and stale helpers left behind by an earlier refactor. (The authenticated
`GET /products` 500 was exactly this: a private `_optional_admin` duplicate of
`app.auth.get_optional_user` that survived the role refactor with the wrong
type.)

Canonical implementations in this repo — use these, do not re-derive them:

| Concern | Canonical home |
| --- | --- |
| Authentication / current user | `backend/app/auth.py` (`get_current_user`, `get_optional_user`) |
| Roles & capabilities | `backend/app/services/roles.py` (`STAFF_ROLES`, `resolve_roles`, `has_capability`) + the `Staff*` aliases in `auth.py` |
| Password hashing / JWT | `backend/app/security.py` |
| Totals, shipping, discount | `backend/app/services/pricing.py` (`shipping_fee`, `quote`) |
| Coupon lookup / normalisation / limits | `backend/app/services/coupons.py` |
| Checkout & stock decrement | `backend/app/services/checkout.py` |
| Order transitions, cancel, stock restore | `backend/app/services/order_lifecycle.py` (`ALLOWED_STATUS_TRANSITIONS`, `CANCELLABLE_STATUSES`, `assert_transition`, `restore_stock`, `cancel_order_tx`) |
| Payments / refunds / simulation mode | `backend/app/services/payments.py` |
| Pagination envelope | `backend/app/services/pagination.py` (frontend side: `toPage()` in `src/lib/api.ts`) |
| Audit logging | `backend/app/services/audit.py` |
| Client IP (audit trail, throttles) | `backend/app/services/client_ip.py` (`resolve_client_ip`; XFF only from `TRUSTED_PROXIES`), stored per request in `audit.client_ip_ctx` |
| Contact-form abuse guard | `backend/app/services/contact_guard.py` (`record_attempt`) |
| Customer notifications (in-app + SMS/email outbox), channel switches | `backend/app/services/notifications.py` (`notify_order_event`, `notify_refund_event`, `notify`, `load_switches`); providers only behind it in `notification_providers.py` — never call Kavenegar/SMTP from a router |
| Startup DDL | `startup_ddl()` in `backend/app/db.py` |
| All frontend HTTP | `vogue-vintage-vibes/src/lib/api.ts` (the `api` object + `request()`) |
| Frontend auth/session | `src/lib/auth.tsx` |
| Currency/number formatting | `src/lib/format.ts` (`formatPrice`), spec B4.1 |

No frontend file may call `fetch` against the backend directly; it goes through
`src/lib/api.ts`. No new backend module may re-implement a row in that table.

## Rule 8 — Contract first for any change crossing a boundary

Applies to every backend change with a frontend consumer, and every frontend
change that reads new backend data. Before editing, state explicitly:

- request shape (path/query/body) and response shape;
- status codes for success **and** failure, and the error body shape used by
  `request()` in `src/lib/api.ts`;
- authentication requirement and ownership rule;
- pagination behaviour (bare array vs. the `Page<T>` envelope — `toPage()`
  tolerates both, so verify which one the endpoint actually returns);
- normalisation rules (e.g. coupon codes are trimmed and upper-cased — that must
  be identical in validation *and* redemption);
- every existing consumer (Rule 6 blast radius).

Do not change an existing response shape because a cleaner one seems preferable.
Keep the contract backwards-compatible unless the user explicitly asks for a
breaking change; if you must break it, update every consumer in the same task and
say so in the audit.

## Rule 9 — Security boundary before happy path (backend + any privileged UI)

For every new or modified endpoint, and every privileged mutation, answer these
before writing the happy path:

1. Who can call it — anonymous, customer, which staff capability, admin?
2. Which resources may that caller reach?
3. Is the resource actually **owned** by the caller, checked in the query?
4. Is this specific mutation allowed for that role/capability?
5. Can a **stale JWT** or a client-supplied field (role, price, user id, status)
   bypass the check? Roles come from `user_roles` via `resolve_roles()` — never
   from the token's `role` claim beyond the harmless `customer` default.
6. Can an id belonging to another user be supplied and accepted?
7. Can the call be repeated (Rule 10)?
8. Can it be called in an invalid state (Rule 10)?

**The backend is the only authority.** Hidden navigation, disabled buttons,
route guards and client-side validation are UX, never authorization — but a
protected admin route must *also* handle direct URL entry and render the Persian
permission notice rather than an empty state.

**Authorization testing is multi-actor.** Do not verify only with the intended
user or only by clicking through the UI. Where relevant, exercise: anonymous, a
normal customer, each relevant staff role, admin, a wrong-owner resource, and an
invalid/stale credential — and for frontend routes, direct navigation to the URL
plus a refresh.

## Rule 10 — Statuses are state machines; repeats must be safe (backend)

Order status, payment status, refund status, contact-message status and stock
state are **not** free-form fields. Before changing any status behaviour,
identify from `order_lifecycle.py` / `payments.py`: the allowed transitions,
which states are terminal, what a repeated transition does, which backward
transitions are invalid, the side effects of each transition, and the
role/ownership required. Keep using the Rule 4 vocabulary; express new behaviour
*in terms of* the existing strings.

Then answer, in writing: **"what happens if this exact operation runs twice?"**
Ask it for payments, refunds and settlements, order cancellation, stock changes,
role changes, gateway callbacks/webhooks, audit rows, and seed scripts. A second
identical call must not move money twice, move stock twice, grant a permission
twice, or fire an external side effect twice. Prefer: terminal states reject with
409, a no-op repeat succeeds silently, side effects fire only on the actual
transition.

## Rule 11 — Money and inventory are invariants (backend, with frontend)

Never touch checkout, payment, refund, cancellation, coupon, pricing or stock
logic without first naming the invariants at risk. Consider at minimum:
server-side pricing, client price manipulation, coupon normalisation, coupon
usage limits, duplicate settlement, payment idempotency, stock decrement, stock
restoration, cancellation, variants, concurrent checkout, transaction boundaries
and terminal states.

The frontend never becomes the source of truth for a financial value: it may
display a quote, but `backend/app/services/pricing.py` computes the authoritative
totals and `checkout.py` re-validates them against the database at order time.
Rule 4's money rules (۸۹٬۰۰۰ shipping, free ≥ ۲٬۰۰۰٬۰۰۰ tomans) and status
strings stay unchanged without an explicit user decision.

Any change affecting money or inventory **must add or update a test covering the
invariant** in `backend/tests/` (the natural homes are
`test_pricing_and_coupons.py` and `test_variants.py`).

## Rule 12 — Minimal diff

Make the smallest change that correctly solves the requested problem. Do not
refactor unrelated code, rename unrelated APIs, reformat unrelated files, upgrade
dependencies without necessity, rewrite working modules, or clean up unrelated
technical debt. Unnecessary edits are the main source of regressions.

If you discover an unrelated problem, do **not** fix it silently: add a checkbox
to the right file under Rule 2 and mention it in the audit under *What is NOT
done / open*. One exception stands: a formatter run that the lint gate requires
(`bun run format`) may touch unrelated files — say so explicitly in the audit.

## Rule 13 — Verify the behaviour you changed, in this order

Run the checks from narrow to wide, and only claim what you ran:

1. The most targeted test for the changed behaviour
   (`cd backend && ./.venv/bin/python -m pytest -q tests/test_<x>.py`).
2. The full backend suite: `./.venv/bin/python -m pytest -q`.
3. Lint: `./.venv/bin/python -m ruff check app tests`; frontend:
   `cd vogue-vintage-vibes && bun run lint` and, for build-affecting changes,
   `bun run build`.
4. For API changes, against a running stack:
   `./.venv/bin/python tests/api_smoke.py`.
5. For anything a user can see or an operator can run — UI, Docker, startup —
   exercise the real runtime path (browser, `curl`, `docker compose logs`), not
   only the test suite.

**Error paths are part of the feature.** Beyond the happy path, cover: invalid
input, unauthorized caller, forbidden caller, missing resource, a duplicate or
repeated request, an invalid state, a dependency failure, an empty result, and
boundary values. For UI work additionally check: loading, empty, error, mobile,
desktop, direct URL, refresh, and a failed/stale API response.

**Prohibited:** reporting "tests passed" when the relevant suite was not
executed; writing a hollow test just to turn the suite green; and **weakening a
validation rule to make a test pass**. When a test fails against an invariant,
first decide which of these is wrong — the test, the caller, the contract, or the
implementation — and fix that. Security and business invariants only change on an
explicit user decision.

## Rule 14 — Clean-environment verification (infra, DB, seeds, config)

Whenever a change touches Docker, `infra/initdb/`, `startup_ddl()` in
`backend/app/db.py`, any `app/seed_*.py`, environment configuration, startup
ordering, or `depends_on` conditions, a working local database is **not**
evidence. Verify from a clean state:

```
cd infra
docker compose down -v
docker compose up -d --build
docker compose logs db-init        # must exit 0, all four seed stages
docker compose ps                  # postgres + minio healthy
curl -fsS http://localhost:8000/health
```

Note that `db-init` and `backend` start in parallel — `db-init` waits only on
Postgres — so every seed module must call `startup_ddl()` itself and must not
rely on the API container having booted first. Seeds must also be idempotent
(Rule 10): a re-run must not duplicate data.

Before diagnosing any runtime or database bug, first ask whether the environment
is dirty: stale containers, stale volumes, old seed data, DDL that predates the
current `startup_ddl()`, cached frontend artifacts, outdated dependencies, or
hand-edited `infra/.env`. If the bug could be environment-dependent, reproduce it
from a clean state before concluding the implementation is correct — and equally,
do not trust a green run that came from a dirty environment.

## Rule 15 — Document what actually happened (extends Rules 1 and 5)

Documentation must describe the implementation, not the intention.

Before ticking a checkbox `[x]` in any task file, confirm all four: the
implementation exists; tests exist where Rules 11/13 require them; the
verification was actually performed; and every acceptance criterion in the task
or spec section is met. If only part of a task is done, leave it `[ ]` or `[~]`
and record the delivered part in the audit — never tick a partially implemented
task.

State the verification level honestly in the audit, using these words:
*implemented* (code written, not run) · *locally tested* (unit tests pass) ·
*integration tested* (`api_smoke.py` against a running stack) · *browser tested*
(exercised in a real browser) · *clean-environment tested* (Rule 14 from
`down -v`) · *fully verified* (all of the above). An audit must never claim a
stronger level than what was performed. "I ran the suite" is not "I verified the
feature".
