# Master Backlog — SÂNDÉ / Barin Shop

> **Canonical execution backlog for coding agents.**
>
> This file consolidates the current repository state, `plan/backend-tasks.md`,
> `plan/frontend-tasks.md`, `plan/ADMIN-BACKEND_TASKS.md`,
> `plan/ADMIN-FRONTEND_TASKS.md`, and the full audit
> `plan/audit/2026-09-22-full-backlog-audit.md`.
>
> **Rule:** Agents execute from this file for remaining work. The older task/spec
> documents remain historical/source documents and must not be treated as a second
> independent queue.

## 1. Scope and source of truth

The live repository architecture is authoritative:

* Backend: FastAPI + async SQLAlchemy + PostgreSQL.
* Authentication: repository-owned HS256 JWT.
* Authorization: `user_roles` + capability guards.
* Storage: MinIO through `/storage/upload-url` and `/storage/sign`.
* Frontend: TanStack Start / React.
* Frontend data layer: `src/lib/api.ts`.
* No Supabase, Postgres RPC, RLS, or `createServerFn` implementation exists.

The dev spec contains stale Supabase/RLS/RPC wording in several places. Do not
reintroduce those mechanisms. Follow the live repository and Rules 0–15.

## 2. Master status model

Use these statuses in this file:

* `TODO` — ready for an agent to execute.
* `BLOCKED` — cannot be implemented correctly until the listed decision is made.
* `IN_PROGRESS` — an agent currently owns the task.
* `DONE` — implementation + required verification completed and audit written.
* `DROPPED` — explicitly removed by product decision.
* `OBSOLETE` — retained only for traceability; never execute.

Priority:

* **P0** — correctness / inventory / financial / security / data corruption.
* **P1** — core product functionality.
* **P2** — quality / scalability / operability.
* **P3** — future / nice-to-have.

## 3. Agent execution contract

Before starting a task:

1. Read `design/SANDE_FULL_DEV_SPEC.md`.
2. Read `AGENTS.md` and `plan/RULES.md`.
3. Read this file and the source task/spec entry for the selected task.
4. Inspect the live implementation and trace the full contract before modifying it.
5. Confirm the task is still `TODO` and that all dependencies are satisfied.
6. Do not silently absorb another backlog item into the current task.

While implementing:

* Reuse canonical helpers and existing data flows.
* Do not add parallel auth, role, pricing, API, storage, or state-machine systems.
* Do not change frozen status strings or cart money rules.
* Treat money and inventory changes as transactional invariants.
* Prefer the smallest diff that completely fixes the selected task.
* Preserve backward compatibility unless the task explicitly changes the contract.
* If a newly discovered requirement is outside the task, stop and create/update a
  backlog entry rather than expanding scope silently.

Before marking `DONE`:

1. Run focused tests for the changed behavior.
2. Run relevant backend/frontend/infra verification according to Rules 13–14.
3. Exercise failure/error paths, not only the happy path.
4. For DB/seed/infra changes, verify from a clean environment.
5. Write `plan/audit/YYYY-MM-DD-<task-slug>.md`.
6. Update the original task checkbox/document as required by Rules 1 and 5.
7. Append to `plan/session-log.md`.
8. Update this file:

   * `TODO → DONE`
   * add the audit link
   * record verification level
   * update dependency availability if another task is unblocked.
9. Commit and push the complete task.

**Do not mark DONE merely because code exists.**

## 4. Critical ordering

### First task

`B6.8` must be completed before:

* `AB-BE-01`
* `B4.9`

### Variant-editor dependency

`AB-BE-02` must be completed before:

* `AB-FE-03`

### Notification chain

After decision `D2`:

`B2.1 → F2.3 → B2.5 → B4.13`

### Admin products file collision

`AB-FE-02` and `AB-FE-05` both modify `admin.products.tsx`.
Execute them sequentially unless the agents have explicitly separated file ownership.

## 5. Product / architecture decisions

These are decisions, not implementation tasks.

| ID | Decision                                                          | Blocks                           | Status |
| -- | ----------------------------------------------------------------- | -------------------------------- | ------ |
| D1 | Contact-form abuse control: per-IP throttle, honeypot, or CAPTCHA | B3.11                            | OPEN   |
| D2 | Notification provider and transactional email scope               | B2.1, F2.3, B2.5, B4.13          | OPEN   |
| D3 | CSV import overwrite/skip/upsert semantics + idempotency key      | B2.2a                            | OPEN   |
| D4 | Whether preorder is actually purchasable + fulfilment rules       | B4.13                            | OPEN   |
| D5 | Whether to replace order-time decrement with reserve→commit + TTL | B4.9                             | OPEN   |
| D6 | Whether IBAN/Sheba must be stored as PII                          | future refund UI/storage task    | OPEN   |
| D7 | Product third dimension + customer tier definitions               | B4.8, F3.4b, AB-FE-06 tier badge | OPEN   |
| D8 | Admin data-grid implementation/library                            | F4.3                             | OPEN   |
| D9 | Low-stock rule: configurable per-product threshold vs fixed rule  | documentation only               | OPEN   |

D6 must not generate an implementation task until the PII decision is made.
D9 is documentation/product policy only and does not block current engineering work.

## 6. Master backlog

### P0 — Correctness

#### B6.8 — Per-variant stock restoration on cancellation

* **Layer:** Backend + DB + tests
* **Status:** TODO
* **Dependencies:** none
* **Blocks:** AB-BE-01, B4.9
* **Why:** Variant orders decrement `product_variants.stock`, but cancellation currently
  restores only the aggregate product stock. This silently corrupts inventory.
* **Required implementation:**

  1. Add idempotent `order_items.variant_id UUID REFERENCES product_variants(id) ON DELETE SET NULL`
     in the canonical additive DDL path.
  2. Ensure seed jobs can apply the DDL independently.
  3. Persist `line["variant_id"]` during checkout.
  4. Restore both variant and aggregate stock in one transaction.
  5. Preserve aggregate-only behavior for legacy `NULL` variant rows.
  6. Keep repeated cancellation a no-op.
* **Acceptance tests:**

  * variant order decrements both aggregate and variant stock;
  * cancellation restores both to original values;
  * second cancellation does not inflate either value;
  * legacy NULL variant rows still restore aggregate stock safely.
* **Verification:** live Docker flow + focused pytest + clean-environment DB/seed check.
* **Audit:** create a new task audit; prior audit only established the defect.

---

### P1 — Core product

#### B6.9 — Narrow refund exception handling

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** none
* **Why:** A broad `except Exception` converts unrelated DB/application failures into
  a false "refund already requested" response.
* **Required implementation:** narrow expected duplicate/idempotency handling and let
  unexpected failures surface correctly.
* **Acceptance tests:** successful request, true duplicate, unrelated DB failure.
* **Verification:** focused pytest + API smoke/error-path check.

#### AB-BE-03 — Coupon max discount cap

* **Layer:** Backend + DB + pricing
* **Status:** TODO
* **Dependencies:** none
* **Source:** ADMIN-BACKEND [BE-02]
* **Required implementation:**

  * add `coupons.max_discount_cap`;
  * expose it consistently in schemas/admin CRUD;
  * cap percentage discounts in the canonical pricing path;
  * preserve fixed discounts and existing min-order/usage/date rules;
  * keep checkout and validation calculations identical.
* **Acceptance tests:** percentage below cap, percentage above cap, no cap, fixed coupon.
* **Verification:** pytest + checkout API smoke.

#### F5.5 — Audit-log viewer

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Existing backend:** `GET /admin/audit-logs`
* **Required implementation:**

  * typed `api.ts` client;
  * admin route/view;
  * action/entity/admin filters;
  * pagination/offset;
  * IP + timestamp + old/new values display;
  * role guard;
  * loading, empty and error states.
* **Acceptance:** direct route access respects backend capability.
* **Verification:** frontend type/lint/build + targeted browser/manual flow if available.

#### F5.6 — Role management UI

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Existing backend:** `PUT /admin/users/{id}/roles`
* **Required implementation:**

  * edit role set from users page;
  * confirmation for privilege changes;
  * capability-aware visibility;
  * mutation + cache invalidation;
  * success/error feedback.
* **Rule:** backend role/capability model remains authoritative.
* **Verification:** frontend checks + direct-route authorization scenarios.

#### AB-FE-02 — Admin export controls

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Existing backend:** `/admin/export/orders.{csv,xlsx}`,
  `/admin/export/products.{csv,xlsx}`, `/admin/export/report`
* **Required implementation:**

  * visible export controls;
  * correct format/download handling;
  * date filters where endpoint supports them;
  * loading/error states;
  * capability guard.
* **Important:** do not wait for F4.3.
* **Verification:** browser/download flow + lint/build.

#### AB-FE-05 — Admin products server pagination

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:**

  * use backend pagination for `/admin/products`;
  * preserve filters/search across pages;
  * reset page when filters change;
  * show total/pages and loading state;
  * eliminate whole-table fetch.
* **File collision:** shares `admin.products.tsx` with AB-FE-02.
* **Verification:** network inspection + frontend checks.

#### B3.11 — Contact-form spam guard

* **Layer:** Backend
* **Status:** BLOCKED
* **Decision:** D1
* **Dependencies:** D1
* **Required implementation after decision:** implement the chosen abuse-control
  mechanism without creating a second rate-limit/security framework.
* **Acceptance:** repeated public submissions are controlled; legitimate users still work;
  error response is safe and useful.
* **Verification:** API abuse/error-path test.

#### B2.1 — SMS/email notifications

* **Layer:** Backend
* **Status:** BLOCKED
* **Decision:** D2
* **Dependencies:** D2
* **Required implementation after decision:**

  * chosen provider abstraction;
  * order placed/paid/shipped/cancelled/refund events as in scope;
  * failure/retry semantics;
  * secrets/config handling;
  * no duplicate notifications on repeated state transitions.
* **Blocks:** F2.3, B2.5, B4.13.

#### F2.3 — Forgot password

* **Layer:** Full-stack
* **Status:** BLOCKED
* **Dependencies:** D2 + B2.1
* **Required implementation:**

  * reset token generation/storage/expiry;
  * one-time use;
  * safe user enumeration behavior;
  * email delivery;
  * reset endpoint;
  * frontend request/reset flows.
* **Verification:** focused auth tests + mail transport test/stub + frontend flow.

---

### P2 — Quality / scalability

#### B5.1b — Audit-log DB tamper resistance

* **Layer:** Infra/DB
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:** make `audit_logs` append-only for the application role;
  allow INSERT/SELECT, deny UPDATE/DELETE.
* **Verification:** clean DB bootstrap + negative SQL test + positive audit INSERT.

#### AB-BE-01 — Inventory ledger

* **Layer:** Backend + DB
* **Status:** TODO
* **Dependencies:** B6.8
* **Required implementation:**

  * `inventory_logs` with variant_id/change/reason/created_by/timestamp;
  * canonical writes from purchase/restock/return/manual adjustment paths;
  * no second inventory accounting system.
* **Acceptance:** every supported stock mutation creates exactly one appropriate ledger event.
* **Verification:** pytest + live stock mutation flow.

#### AB-BE-02 — Variant SKU / price / color fields

* **Layer:** Backend + DB + API
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:**

  * unique SKU;
  * nullable `price_override`;
  * `color_hex`;
  * schema/API support;
  * idempotent DDL.
* **Blocks:** AB-FE-03.
* **Verification:** migration/bootstrap + CRUD tests.

#### F5.8 — Remove duplicate /shop catalog fetch

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:** one canonical catalog request path for each shop state;
  avoid simultaneous full catalog + filtered list fetches.
* **Acceptance:** normal shop visit and filtered/search visit issue only required requests.
* **Verification:** network trace + build/type/lint.

#### F5.7 — Admin chart bundle split

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** measurement first
* **Required implementation:** first measure current build, identify actual direct/transitive
  contributors, then route/code split only where evidence supports it.
* **Do not:** assume lodash is a direct dependency or remove it blindly.
* **Verification:** before/after bundle measurement + build.

#### F4.3 — Reusable AdminDataTable

* **Layer:** Frontend
* **Status:** BLOCKED
* **Decision:** D8
* **Required implementation after decision:**

  * canonical table abstraction;
  * search/filter/sort;
  * server pagination;
  * bulk actions;
  * copy helpers;
  * shared toolbar.
* **Important:** exports can be implemented independently by AB-FE-02.
* **Verification:** multiple consuming admin screens, not just the component in isolation.

#### AB-FE-01 — Admin topbar completion

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Required implementation on existing shell:**

  * breadcrumbs;
  * staff profile/avatar menu;
  * command/quick actions where appropriate;
  * storefront preview link;
  * responsive details.
* **Do not rewrite F4.2/AdminLayout.**
* **Verification:** desktop + mobile route navigation and role scenarios.

#### AB-FE-03 — Two-column product editor + RHF/Zod + swatches

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** AB-BE-02
* **Required implementation:**

  * two-column product editor;
  * React Hook Form;
  * Zod schema;
  * variant matrix;
  * SKU;
  * color swatch;
  * size/quantity;
  * price override.
* **Rule:** use existing MinIO upload flow; never direct Supabase storage.
* **Verification:** create/edit validation + persisted backend values.

#### AB-FE-04 — Product image gallery manager

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:**

  * drag/drop;
  * preview;
  * reorder;
  * primary image;
  * delete;
  * progress/retry.
* **Canonical storage:** `POST /storage/upload-url` + `POST /storage/sign` + MinIO.
* **Verification:** upload/reorder/delete on real local stack.

#### F3.5b — Re-check cart stock on window focus

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Required implementation:** re-run stock validation on focus for an open cart;
  maintain server-side checkout validation as the final authority.
* **Verification:** stale stock scenario + focus event.

#### B2.5 — Webhooks + background jobs

* **Layer:** Backend
* **Status:** BLOCKED
* **Decision:** D2
* **Dependencies:** D2
* **Required implementation after decision:**

  * order events;
  * background job mechanism;
  * abandoned-payment reminders;
  * notification integration;
  * idempotency/retry behavior.
* **Verification:** worker execution + restart/retry behavior.

---

### P3 — Future

#### B2.3 — PDF invoices

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** none
* **Before coding:** confirm that server-generated PDF is still required because F4.4
  already provides browser invoice printing.
* **Verification:** generated PDF opens correctly and includes order data.

#### B4.8 — Product model dimension

* **Layer:** Backend + catalog
* **Status:** BLOCKED
* **Decision:** D7(a)
* **Rule:** do not invent a third variant dimension.
* **Verification:** schema + CRUD + filtering + frontend contract if approved.

#### F3.4b — Guest recently viewed

* **Layer:** Frontend
* **Status:** BLOCKED
* **Decision:** D7(c)
* **Likely shape:** localStorage guest history + merge into account history on login.
* **Rule:** use the decision chosen for merge/retention, do not improvise.
* **Verification:** signed-out browse → sign-in → merged display.

#### AB-FE-06 — Customer 360° profile

* **Layer:** Full-stack/frontend
* **Status:** TODO
* **Dependencies:** core profile is unblocked; tier badge depends on D7(b)
* **Required implementation:**

  * customer overview;
  * order history;
  * saved addresses;
  * wishlist;
  * LTV;
  * purchase interval;
  * role management entry point integration.
* **Tier badge:** New/VIP/Wholesale only after D7(b).
* **Verification:** data consistency with existing APIs and capability guards.

#### F1.9 — Lovable preview tooling

* **Layer:** Frontend tooling
* **Status:** TODO
* **Priority:** P3
* **Required implementation:** only if it remains useful after the app is fully independent
  of Lovable; do not reintroduce Lovable/Supabase architecture.

#### B2.2a — CSV product import

* **Layer:** Backend
* **Status:** BLOCKED
* **Decision:** D3
* **Required implementation after decision:**

  * chosen upsert policy;
  * validation/reporting;
  * idempotency;
  * transaction boundaries;
  * error row reporting.
* **Verification:** duplicate input, partial invalid input, retry/idempotency.

#### B4.13 — Preorder fulfilment flag

* **Layer:** Backend
* **Status:** BLOCKED
* **Decisions:** D4 + D2 for notification half
* **Required implementation after decision:**

  * order-level preorder marker;
  * checkout availability semantics;
  * fulfilment semantics;
  * admin visibility;
  * notifications as scoped.
* **Verification:** preorder checkout, fulfilment transitions, cancellation/refund behavior.

## 7. Explicitly not executable

### B2.6 — Coupon admin UI support

* **Status:** OBSOLETE
* **Reason:** superseded by the current backend/admin implementation and F4.5.
* **Action:** do not implement.

### Historical duplicate IDs

`B6.1` appears more than once in `backend-tasks.md`, and `B6.3` overlaps
the order-lifecycle item. This file uses the meaning-specific IDs already established
by the audit. Do not create another B6.x task merely because an old checkbox still
exists.

## 8. Dependency graph

```text
B6.8
├──→ AB-BE-01
└──→ B4.9 (after D5)

AB-BE-02
└──→ AB-FE-03

D1
└──→ B3.11

D2
└──→ B2.1
      ├──→ F2.3
      ├──→ B2.5
      └──→ B4.13 (also D4)

D3
└──→ B2.2a

D5 + B6.8
└──→ B4.9

D7(a)
└──→ B4.8

D7(c)
└──→ F3.4b

D7(b)
└──→ AB-FE-06 tier badge

D8
└──→ F4.3
```

## 9. Recommended agent batches

### Batch A — Critical backend

Run first:

```text
B6.8
B6.9
AB-BE-03
```

B6.8 must finish before AB-BE-01.

### Batch B — Existing admin backend UI gaps

Can run in parallel with Batch A, except AB-FE-02 and AB-FE-05 should not
edit `admin.products.tsx` concurrently:

```text
F5.5
F5.6
AB-FE-02
AB-FE-05
```

### Batch C — Backend quality/infrastructure

```text
B5.1b
AB-BE-01
AB-BE-02
```

AB-BE-01 starts after B6.8.

### Batch D — Frontend quality

```text
F5.8
F5.7
AB-FE-01
AB-FE-04
F3.5b
```

### Batch E — Product editor

```text
AB-FE-03
```

Start only after AB-BE-02.

### Batch F — Decision-gated work

```text
D1 → B3.11
D2 → B2.1 → F2.3 → B2.5 → B4.13
D3 → B2.2a
D5 → B4.9
D7 → B4.8 / F3.4b / AB-FE-06
D8 → F4.3
```

### Batch G — P3

```text
B2.3
F1.9
```

## 10. Count reconciliation

The earlier full audit reported **24 actionable items**, but its priority tables and
existing task files do not reconcile with that number.

For execution purposes this Master Backlog deliberately counts every unique remaining
implementation unit exactly once:

* **19 immediately executable tasks.**
* **10 decision-gated tasks.**
* **29 total remaining implementation units.**
* B2.1 and B4.9 are explicitly included because both exist as real open tasks in the
  repository and were omitted from the audit's headline priority accounting.
* B2.6 is excluded because it is obsolete.
* D1–D9 are decisions, not implementation units.

The old checkbox files are historical and may still show stale `[ ]` markers such as
B6.10. Do not reopen or reimplement work solely because a legacy checkbox is unticked.

## 11. Documentation synchronization

When a task reaches DONE, the agent must synchronize:

1. the relevant checkbox in `backend-tasks.md` or `frontend-tasks.md`;
2. `plan/session-log.md`;
3. a task audit in `plan/audit/`;
4. this Master Backlog;
5. affected README/FEATURES/roadmap/design docs when the task changes their claims.

Known documentation drift to clean deliberately:

* B6.10 is implemented but unticked.
* B2.6 is obsolete but open.
* duplicate B6.1 identifiers exist.
* old ADMIN specs contain Supabase/RLS/RPC mechanism wording.
* some completed backend features originally lacked frontend tracking.

Do not treat documentation cleanup as justification for unrelated code changes.

## 12. Frozen invariants

Agents must not alter these without an explicit product decision:

* Order statuses:
  `pending → processing → shipped → delivered` plus terminal `cancelled`.
* Money rules already established by the project.
* Backend authorization as the authoritative security boundary.
* MinIO storage flow.
* `src/lib/api.ts` as the frontend HTTP/data boundary.

## 13. Audit baseline

Primary source audit:

`plan/audit/2026-09-22-full-backlog-audit.md`

Prior verification reported in that audit came from earlier sessions. Agents must not
claim those checks were rerun unless they actually rerun them.

The audit itself did not execute tests. In particular, B6.8 requires fresh runtime
verification as part of its implementation.

## 14. Current execution pointer

**START HERE: `B6.8`**

After B6.8 is complete, update this section to point to the next highest-priority,
unblocked task.

Last reconciled against:

* `plan/audit/2026-09-22-full-backlog-audit.md`
* `plan/backend-tasks.md`
* `plan/frontend-tasks.md`
* `plan/ADMIN-BACKEND_TASKS.md`
* `plan/ADMIN-FRONTEND_TASKS.md`

Reconciliation date: **2026-09-22**
