# Master Backlog — SÂNDÉ / Barin Shop

> **Canonical execution backlog for coding agents.**
>
> This file consolidates the current repository state, `plan/backend-tasks.md`,
> `plan/frontend-tasks.md`, `plan/ADMIN-BACKEND_TASKS.md`,
> `plan/ADMIN-FRONTEND_TASKS.md`, and the full audit
> `plan/audit/2026-09-22-full-backlog-audit.md`.
>
> **Rule:** Agents execute remaining work from this file. The older task/spec
> documents remain historical/source documents and must not be treated as a
> second independent execution queue.

---

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
reintroduce those mechanisms.

Follow the live repository and Rules 0–15.

---

## 2. Master status model

Use these statuses in this file:

* `TODO` — ready for an agent to execute.
* `IN_PROGRESS` — an agent currently owns the task.
* `DONE` — implementation + required verification completed and audit written.
* `DROPPED` — explicitly removed by product decision.
* `OBSOLETE` — retained only for traceability; never execute.

There are currently **no execution tasks in `BLOCKED` state**.

Priority:

* **P0** — correctness / inventory / financial / security / data corruption.
* **P1** — core product functionality.
* **P2** — quality / scalability / operability.
* **P3** — future / nice-to-have.

---

## 3. Agent execution contract

Before starting a task:

1. Read `design/SANDE_FULL_DEV_SPEC.md`.
2. Read `AGENTS.md` and `plan/RULES.md`.
3. Read this file and the source task/spec entry for the selected task.
4. Inspect the live implementation and trace the full contract before modifying it.
5. Confirm the task is still `TODO` and that all prerequisites are satisfied.
6. Do not silently absorb another backlog item into the current task.

While implementing:

* Reuse canonical helpers and existing data flows.
* Do not add parallel auth, role, pricing, API, storage, or state-machine systems.
* Do not change frozen status strings or cart money rules.
* Treat money and inventory changes as transactional invariants.
* Prefer the smallest diff that completely fixes the selected task.
* Preserve backward compatibility unless the task explicitly changes the contract.
* If a newly discovered requirement is outside the selected task, record it as a
  separate backlog item instead of expanding scope silently.

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
   * record the actual verification level
   * update any newly unblocked dependency information.
9. Commit and push the complete task.

**Do not mark DONE merely because code exists.**

---

# 4. Resolved product / architecture decisions

All previous decisions D1–D9 are now resolved.

Agents must implement these decisions as written and must **not reopen them** unless
a new explicit product decision is added.

## D1 — Contact-form abuse control

**Decision:**

`POST /contact` uses:

* PostgreSQL-backed per-IP throttling.
* Honeypot field.
* No Redis.
* No CAPTCHA.

### Canonical rule

Default throttle:

* maximum **5 contact submissions per IP per 10 minutes**;
* successful/accepted and rejected attempts both count toward the abuse window;
* response must not expose internal rate-limit implementation details;
* authenticated and guest submissions use the same abuse boundary.

The implementation may use a dedicated lightweight PostgreSQL table if no existing
canonical rate-limit primitive exists.

**Unblocks:** `B3.11`.

---

## D2 — Notification provider and scope

**Decision:**

* **SMS:** Kavenegar.
* **Email:** SMTP.
* Use a small provider abstraction so the transport can be replaced later without
  changing business logic.

### Transactional notification scope

Implement only transactional notifications:

* order created;
* payment confirmed;
* order shipped;
* order cancelled;
* refund approved/settled;
* password-reset email;
* preorder-related notification required by the final preorder workflow.

No marketing/newsletter/campaign notification system is part of this backlog.

### Requirements

* provider failures must not corrupt order/payment/refund state;
* repeated lifecycle operations must not send duplicate notifications;
* secrets belong in environment/configuration;
* business logic must call a canonical notification service rather than Kavenegar
  or SMTP directly from multiple routers.

**Unblocks:** `B2.1`, `F2.3`, `B2.5`, `B4.13`.

---

## D3 — CSV product import semantics

**Decision:**

CSV import is an **idempotent upsert**.

### Matching order

1. If a valid `product_id` exists in the CSV, use it as the canonical key.
2. Otherwise use normalized `name + category` as the match key.

Normalization must be deterministic:

* trim whitespace;
* normalize case;
* normalize repeated internal whitespace;
* use the existing project/category representation where available.

### Update behavior

Only fields actually supplied in the CSV are updated.

An omitted field must **not** erase an existing value.

### Duplicate behavior

Duplicate canonical keys inside the same CSV are rejected as an import validation
error instead of being processed unpredictably.

### Import transaction

The import must provide deterministic results and be safe to retry.

**Unblocks:** `B2.2a`.

---

## D4 — Preorder policy

**Decision:**

Preorders are supported and purchasable.

### Rules

* `availability=preorder` is orderable.
* A preorder does **not** decrement physical stock.
* The order item stores an explicit preorder marker.
* The existing frozen order statuses remain unchanged.
* Payment follows the current checkout/payment flow.
* Once the product reaches its `available_at`/fulfillment point, the order becomes
  operationally fulfillable.
* No speculative automatic fulfillment worker is required for the first implementation.
* Admin workflows must clearly identify preorder items.

Cancellation/refund behavior must follow the same existing order lifecycle and
financial invariants.

Notifications use the D2 notification path where applicable.

**Unblocks:** `B4.13`.

---

## D5 — Stock reservation with TTL

**Decision:**

Do **not** implement stock reservation with TTL in the current roadmap.

The canonical model remains:

```text
checkout
  ↓
create order
  ↓
decrement stock transactionally
```

The system will not introduce:

```text
reserve
  ↓
TTL
  ↓
commit/release
```

until the real asynchronous payment/redirect architecture creates a concrete
business requirement for reservation.

**Result:** `B4.9` is **DROPPED**.

---

## D6 — Refund banking information

**Decision:**

Do **not** store:

* IBAN;
* Sheba;
* card number;
* other customer payout banking details.

Refund settlement remains operational/out-of-band.

The system stores only:

* refund status;
* resolver;
* resolution timestamp;
* bank/payment tracking code.

**Result:** no IBAN/Sheba implementation task is created.

---

## D7(a) — Product variant dimensions

**Decision:**

Variants remain:

```text
Size × Color
```

No third product variant axis is introduced.

Do not invent:

* model;
* material;
* style;
* length;
* fit;
* or any other third dimension.

**Result:** `B4.8` is **DROPPED**.

---

## D7(b) — Customer tiers

Customer tiers are:

### New

Fewer than **3 delivered orders**.

### VIP

**3 or more delivered orders**.

### Wholesale

Explicitly assigned by staff.

Wholesale takes precedence over automatic New/VIP calculation.

The tier is a customer classification, not a backend authorization role.

Therefore:

```text
role != tier
```

A Wholesale customer is not automatically an admin/staff user.

`AB-FE-06` must use these semantics.

If the current schema has no canonical field for the explicit Wholesale flag,
the task may add the smallest appropriate customer-tier representation as part
of `AB-FE-06`, without introducing a second role system.

---

## D7(c) — Guest recently viewed

Guest recently-viewed is stored in `localStorage`.

Rules:

* maximum **8 products**;
* store product IDs and most recent view timestamps;
* deduplicate by product ID;
* newest view wins;
* when the user signs in, guest history merges with account history;
* server/account history remains authoritative after merge;
* no new backend DELETE endpoint is required for this task.

**Unblocks:** `F3.4b`.

---

## D8 — Admin data grid

**Decision:**

Use:

```text
@tanstack/react-table
```

as the canonical implementation for `AdminDataTable`.

### Rules

* table state is controlled;
* search/filter/sort state is explicit;
* pagination is server-side where the backend supports it;
* bulk actions operate through existing/canonical API mutations;
* no second table abstraction should be created.

**Unblocks:** `F4.3`.

---

## D9 — Low-stock policy

**Decision:**

The canonical low-stock rule is:

```text
product.low_stock_threshold
```

per product.

Do **not** implement the stale fixed rule:

```text
stock < 5
```

The product-configurable threshold remains authoritative.

No new implementation task is needed.

---

# 5. Critical ordering

## First task

`B6.8` is **DONE** (2026-09-22), so its dependent is released:

* `AB-BE-01` — unblocked

`B4.9` is no longer part of execution because it is DROPPED.

## Variant editor dependency

`AB-BE-02` must be completed before:

* `AB-FE-03`

## Notification chain

The notification tasks are now unblocked:

```text
B2.1
├──→ F2.3
├──→ B2.5
└──→ B4.13
```

## Admin products file collision

`AB-FE-02` and `AB-FE-05` both modify
`admin.products.tsx`.

Execute them sequentially unless file ownership is explicitly separated.

---

# 6. Machine-readable task index

> This JSON block is the canonical machine-readable representation of the
> executable backlog. Agents may parse this block instead of extracting task
> metadata from the prose sections below.
>
> Rules:
>
> * Every executable task appears exactly once.
> * `status` must match the prose section.
> * `depends_on` contains only task IDs, not product decisions.
> * Resolved decisions are represented in task descriptions, not as blockers.
> * `blocks` contains downstream task IDs.
> * `batch` identifies the recommended execution batch.
> * `priority` is one of `P0`, `P1`, `P2`, `P3`.

```json
{
  "schema_version": "1.0",
  "backlog_version": "2026-09-22",
  "repository": "bhrlu/barin-shop",
  "branch": "main",
  "source_of_truth": "plan/MASTER-BACKLOG.md",
  "execution_policy": {
    "blocked_tasks": 0,
    "agent_start_task": "F5.5",
    "one_task_at_a_time": true,
    "verify_before_done": true,
    "audit_required": true,
    "session_log_required": true
  },
  "tasks": [
    {
      "id": "B6.8",
      "title": "Per-variant stock restoration on cancellation",
      "priority": "P0",
      "status": "DONE",
      "layer": "backend_db_tests",
      "depends_on": [],
      "blocks": ["AB-BE-01"],
      "batch": "A",
      "source": "backend-tasks.md",
      "scope": "Add order_items.variant_id, persist it during checkout, restore variant and aggregate stock atomically, preserve legacy NULL behavior, and prove cancellation is idempotent.",
      "audit": "plan/audit/2026-09-22-b68-variant-stock-restore.md",
      "verification_level": "fully verified",
      "completed": "2026-09-22"
    },
    {
      "id": "B6.9",
      "title": "Narrow refund exception handling",
      "priority": "P1",
      "status": "DONE",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "A",
      "source": "backend-tasks.md",
      "scope": "Replace broad refund exception swallowing with explicit duplicate/idempotency handling and preserve unexpected failures.",
      "audit": "plan/audit/2026-09-22-b69-refund-exception-handling.md",
      "verification_level": "integration tested",
      "completed": "2026-09-22"
    },
    {
      "id": "AB-BE-03",
      "title": "Coupon max discount cap",
      "priority": "P1",
      "status": "DONE",
      "layer": "backend_db_pricing",
      "depends_on": [],
      "blocks": [],
      "batch": "A",
      "source": "ADMIN-BACKEND_TASKS.md:BE-02",
      "scope": "Add max_discount_cap and apply it consistently in validation, pricing, checkout, and coupon admin CRUD.",
      "audit": "plan/audit/2026-09-22-abbe03-coupon-max-discount-cap.md",
      "verification_level": "fully verified",
      "completed": "2026-09-22"
    },
    {
      "id": "F5.5",
      "title": "Audit-log viewer",
      "priority": "P1",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "frontend-tasks.md",
      "scope": "Add typed API access and an authorized admin audit-log viewer with filters, pagination, old/new values, IP, loading, empty, and error states."
    },
    {
      "id": "F5.6",
      "title": "Role management UI",
      "priority": "P1",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "frontend-tasks.md",
      "scope": "Manage staff role sets from the users page using the canonical backend capability model."
    },
    {
      "id": "AB-FE-02",
      "title": "Admin export controls",
      "priority": "P1",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "ADMIN-FRONTEND_TASKS.md plus audit-derived task",
      "scope": "Expose existing order/product CSV/XLSX/report exports with correct download handling, filters, loading/error states, and capability guards."
    },
    {
      "id": "AB-FE-05",
      "title": "Admin products server pagination",
      "priority": "P1",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "ADMIN-FRONTEND_TASKS.md plus audit-derived task",
      "scope": "Use server pagination for admin products, preserve filters, reset page when filters change, and stop full-table fetching."
    },
    {
      "id": "B3.11",
      "title": "Contact-form spam guard",
      "priority": "P1",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Implement PostgreSQL-backed per-IP throttling at 5 requests per 10 minutes plus honeypot; no Redis or CAPTCHA."
    },
    {
      "id": "B2.1",
      "title": "SMS/email notifications",
      "priority": "P1",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": ["F2.3", "B2.5", "B4.13"],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Build a replaceable transactional notification service using Kavenegar for SMS and SMTP for email."
    },
    {
      "id": "F2.3",
      "title": "Forgot password",
      "priority": "P1",
      "status": "TODO",
      "layer": "fullstack",
      "depends_on": ["B2.1"],
      "blocks": [],
      "batch": "F",
      "source": "frontend-tasks.md",
      "scope": "Implement secure reset tokens, expiry, one-time use, email delivery, backend reset API, request UI, and reset UI."
    },
    {
      "id": "B5.1b",
      "title": "Audit-log DB tamper resistance",
      "priority": "P2",
      "status": "TODO",
      "layer": "infra_db",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "scope": "Make audit_logs append-only for the application role with positive INSERT/SELECT and negative UPDATE/DELETE verification."
    },
    {
      "id": "AB-BE-01",
      "title": "Inventory ledger",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend_db",
      "depends_on": ["B6.8"],
      "blocks": [],
      "batch": "C",
      "source": "ADMIN-BACKEND_TASKS.md:BE-01",
      "scope": "Create inventory_logs and record canonical purchase, restock, return, and manual-adjustment events."
    },
    {
      "id": "AB-BE-02",
      "title": "Variant SKU / price / color fields",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend_db_api",
      "depends_on": [],
      "blocks": ["AB-FE-03"],
      "batch": "C",
      "source": "ADMIN-BACKEND_TASKS.md:BE-01",
      "scope": "Add unique SKU, nullable price_override, color_hex, schemas, CRUD support, and idempotent DDL."
    },
    {
      "id": "F5.8",
      "title": "Remove duplicate /shop catalog fetch",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "scope": "Establish one canonical shop catalog request path and eliminate unnecessary full-catalog fetches."
    },
    {
      "id": "F5.7",
      "title": "Admin chart bundle split",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "scope": "Measure the actual production bundle first, then apply evidence-based chart route/code splitting and re-measure."
    },
    {
      "id": "F4.3",
      "title": "Reusable AdminDataTable",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "frontend-tasks.md",
      "scope": "Build the canonical admin table abstraction with @tanstack/react-table, controlled server-side state, filters, sorting, pagination, bulk actions, and copy helpers."
    },
    {
      "id": "AB-FE-01",
      "title": "Admin topbar completion",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "ADMIN-FRONTEND_TASKS.md:FE-01",
      "scope": "Complete breadcrumbs, profile/avatar actions, command/quick actions, storefront preview, and responsive details without rewriting the existing shell."
    },
    {
      "id": "AB-FE-03",
      "title": "Two-column product editor + RHF/Zod + swatches",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": ["AB-BE-02"],
      "blocks": [],
      "batch": "E",
      "source": "ADMIN-FRONTEND_TASKS.md:FE-04",
      "scope": "Implement two-column product editor, React Hook Form, Zod, variant matrix, SKU, swatches, size, quantity, and price override."
    },
    {
      "id": "AB-FE-04",
      "title": "Product image gallery manager",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "ADMIN-FRONTEND_TASKS.md:FE-04",
      "scope": "Implement drag/drop, preview, reorder, primary-image selection, delete, progress, and retry using MinIO APIs."
    },
    {
      "id": "F3.5b",
      "title": "Re-check cart stock on window focus",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "scope": "Re-run server stock validation when an open cart window regains focus while preserving checkout as final authority."
    },
    {
      "id": "B2.5",
      "title": "Webhooks + background jobs",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": ["B2.1"],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Add order events, background jobs, abandoned-payment reminders, notification integration, idempotency, and retry behavior."
    },
    {
      "id": "B2.3",
      "title": "PDF invoices",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "G",
      "source": "backend-tasks.md",
      "scope": "Implement server-generated PDF invoices only if still required after the existing browser invoice flow is confirmed insufficient."
    },
    {
      "id": "F3.4b",
      "title": "Guest recently viewed",
      "priority": "P3",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "frontend-tasks.md",
      "scope": "Store up to 8 guest product IDs/timestamps in localStorage and merge deterministically into account history on sign-in."
    },
    {
      "id": "AB-FE-06",
      "title": "Customer 360° profile",
      "priority": "P3",
      "status": "TODO",
      "layer": "fullstack_frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "ADMIN-FRONTEND_TASKS.md:FE-08",
      "scope": "Customer overview, orders, addresses, wishlist, LTV, purchase interval, role entry point, and New/VIP/Wholesale tier display."
    },
    {
      "id": "F1.9",
      "title": "Lovable preview tooling",
      "priority": "P3",
      "status": "TODO",
      "layer": "frontend_tooling",
      "depends_on": [],
      "blocks": [],
      "batch": "G",
      "source": "frontend-tasks.md",
      "scope": "Only implement if useful after Lovable is fully out of the runtime architecture; never reintroduce Lovable/Supabase dependencies."
    },
    {
      "id": "B2.2a",
      "title": "CSV product import",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Implement idempotent upsert using product_id when supplied, otherwise normalized name+category, with partial-field updates and duplicate rejection."
    },
    {
      "id": "B4.13",
      "title": "Preorder fulfilment flag",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": ["B2.1"],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Allow preorder checkout, persist preorder marker, avoid physical stock decrement, expose preorder state to admin, and integrate applicable notifications."
    },
    {
      "id": "NEW-B68-1",
      "title": "Drop the redundant information_schema probe in restore_stock()",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": ["B6.8"],
      "blocks": [],
      "batch": "F",
      "source": "discovered-during-B6.8",
      "scope": "order_items.variant_id is now always created by startup_ddl(), so the per-cancellation column-existence query in order_lifecycle.restore_stock() can be removed once every deployed stack has run the new DDL."
    },
    {
      "id": "NEW-B69-1",
      "title": "Narrow the remaining bare except Exception handlers in products/storage routers",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "E",
      "source": "discovered-during-B6.9",
      "scope": "routers/products.py turns any failure in four CRUD handlers into a 409 duplicate message, and routers/storage.py has two broad handlers to review; apply the B6.9 shape (IntegrityError + SQLSTATE 23505 only, re-raise the rest)."
    },
    {
      "id": "NEW-ABBE03-1",
      "title": "Coupon discount-cap field in the admin dialog",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": ["AB-BE-03"],
      "blocks": [],
      "batch": "B",
      "source": "discovered-during-AB-BE-03",
      "scope": "Expose coupons.max_discount_cap in the F4.5 admin coupon dialog (admin.coupons.tsx) and in the AdminCoupon / adminCreateCoupon / adminUpdateCoupon types in src/lib/api.ts, including the 0-clears-the-ceiling semantics. Tracked as F5.9 in frontend-tasks.md."
    }
  ],
  "excluded": [
    {
      "id": "B4.8",
      "status": "DROPPED",
      "reason": "Product variants remain Size × Color; no third dimension."
    },
    {
      "id": "B4.9",
      "status": "DROPPED",
      "reason": "Current payment architecture does not justify stock reservation with TTL."
    },
    {
      "id": "B2.6",
      "status": "OBSOLETE",
      "reason": "Superseded by the existing backend coupon system and F4.5."
    }
  ],
  "counts": {
    "total_executable": 30,
    "done": 3,
    "open": 27,
    "P0": 0,
    "P1": 7,
    "P2": 13,
    "P3": 7,
    "blocked": 0,
    "dropped": 2,
    "obsolete": 1,
    "open_product_decisions": 0
  }
}
```

---

# 7. Master backlog

## P0 — Correctness

### B6.8 — Per-variant stock restoration on cancellation

* **Layer:** Backend + DB + tests
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Blocks:** AB-BE-01 — now unblocked
* **Audit:** [`plan/audit/2026-09-22-b68-variant-stock-restore.md`](audit/2026-09-22-b68-variant-stock-restore.md)
* **Verification level:** fully verified (focused + full pytest, ruff,
  `api_smoke.py`, live HTTP checkout/cancel on both cancel entry points,
  clean-environment `docker compose down -v` DDL proof)
* **Delivered:** `order_items.variant_id` added through `CATALOG_DDL` in
  `app/db.py` (all five seed modules already call `startup_ddl()`), written by
  `services/checkout.py`, consumed by the existing
  `order_lifecycle.restore_stock()`; legacy `NULL` rows still restore the
  aggregate only and a repeated cancellation moves no stock.
  `backend/tests/test_order_lifecycle_stock.py` covers the four acceptance tests.
* **Not delivered:** historical `order_items` rows are not backfilled with a
  guessed `variant_id`; `[BE-01]`'s `inventory_logs` ledger remains AB-BE-01.
* **Why:** Variant orders decrement `product_variants.stock`, but cancellation currently
  restores only aggregate product stock. This silently corrupts inventory.

### Required implementation

1. Add idempotent:

   ```sql
   ALTER TABLE public.order_items
   ADD COLUMN IF NOT EXISTS variant_id UUID
   REFERENCES public.product_variants(id)
   ON DELETE SET NULL;
   ```

   through the canonical additive DDL path.

2. Ensure seed jobs can independently apply the DDL.

3. Persist `line["variant_id"]` during checkout.

4. Restore both variant and aggregate stock in one transaction.

5. Preserve aggregate-only behavior for legacy `NULL` variant rows.

6. Repeated cancellation must remain a no-op.

### Acceptance tests

* variant order decrements both aggregate and variant stock;
* cancellation restores both to original values;
* second cancellation does not inflate either value;
* legacy `NULL` variant rows still behave safely.

### Verification

* focused pytest;
* live Docker checkout/cancel flow;
* clean-environment DB/seed verification.

---

# P1 — Core product

## B6.9 — Narrow refund exception handling

* **Layer:** Backend
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Audit:** [`plan/audit/2026-09-22-b69-refund-exception-handling.md`](audit/2026-09-22-b69-refund-exception-handling.md)
* **Verification level:** integration tested (10 new unit + DB-backed endpoint
  tests, full pytest 54 passed, ruff clean, `api_smoke.py` 196/0, plus a live
  HTTP request/duplicate/401/404 flow on the rebuilt container). Rule 14
  clean-environment proof not repeated: no DDL, seed, Docker or config change.
* **Delivered:** `request_refund` catches `IntegrityError` and returns the
  unchanged 409 only for SQLSTATE `23505`; every other failure is logged and
  re-raised, so a real database fault surfaces as a 500 instead of a false
  "already requested". Success and duplicate contracts are byte-identical.
* **Not delivered:** the 500 carries FastAPI's generic body (intended); the same
  broad-handler pattern still exists in `routers/products.py` /
  `routers/storage.py` and was recorded as `NEW-B69-1` rather than fixed here.

### Problem

A broad:

```python
except Exception:
```

currently turns unrelated failures into a false "refund already requested" response.

### Required implementation

* catch only the expected duplicate/idempotency condition;
* preserve legitimate duplicate behavior;
* unexpected DB/application errors must surface correctly;
* preserve security and error response conventions.

### Acceptance tests

* successful refund request;
* true duplicate request;
* unrelated DB failure.

### Verification

Focused pytest + API error-path smoke test.

---

## AB-BE-03 — Coupon max discount cap

* **Layer:** Backend + DB + pricing
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Source:** ADMIN-BACKEND `[BE-02]`
* **Audit:** [`plan/audit/2026-09-22-abbe03-coupon-max-discount-cap.md`](audit/2026-09-22-abbe03-coupon-max-discount-cap.md)
* **Verification level:** fully verified (16 new/updated tests, full pytest 70
  passed, ruff clean, `api_smoke.py` 196/0, live admin+customer HTTP flow, and a
  `docker compose down -v` clean-environment proof of the DDL and seeds)
* **Delivered:** nullable `coupons.max_discount_cap INTEGER` (CHECK > 0) via
  `COUPON_DDL`; the clamp lives in `services/coupons.py::compute_discount`, the
  one function both `POST /coupons/validate` and checkout reach, so the quote and
  the order always agree. Percent-off only — a fixed `amount_off` is already its
  own ceiling — and NULL keeps today's behaviour for every seeded coupon.
  Exposed in `CouponOut`/`CouponCreate`/`CouponUpdate`, the admin list and the
  create-audit entry; `PATCH` with `0` clears the ceiling.
* **Deviation:** the clamp is in `compute_discount`, not `pricing.py` as the
  2026-09-22 full-backlog audit proposed — `quote()` takes an already computed
  discount, so clamping there would have needed a second copy for the validate
  endpoint (Rule 7).
* **Not delivered:** no admin UI field yet (`NEW-ABBE03-1` / `F5.9`); fixed
  `amount_off` coupons stay deliberately uncapped.

### Required implementation

* add `coupons.max_discount_cap`;
* expose it in schemas and admin CRUD;
* cap percentage discounts in the canonical pricing path;
* preserve fixed discounts;
* preserve min-order, usage and date rules;
* use the same calculation rules in coupon validation and checkout.

### Acceptance tests

* percentage discount under cap;
* percentage discount over cap;
* percentage without cap;
* fixed discount;
* checkout and validation produce identical discount values.

### Verification

Pytest + checkout API smoke.

---

## F5.5 — Audit-log viewer

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Backend:** `GET /admin/audit-logs`

### Required implementation

* typed `api.ts` method;
* dedicated admin route/view;
* action filter;
* entity filter;
* admin filter;
* pagination/offset;
* timestamp;
* IP address;
* old/new values;
* role guard;
* loading state;
* empty state;
* error state.

### Acceptance

Direct route entry must respect backend capabilities.

### Verification

Typecheck + lint + build + targeted browser/manual verification.

---

## F5.6 — Role management UI

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none
* **Backend:** `PUT /admin/users/{id}/roles`

### Required implementation

* role-set editor in `/admin/users`;
* confirmation for privilege changes;
* capability-aware visibility;
* mutation handling;
* cache invalidation;
* success/error feedback.

### Rule

The backend role/capability model is authoritative.

Do not implement a separate frontend-only permission model.

### Verification

Frontend checks + direct URL authorization scenarios.

---

## AB-FE-02 — Admin export controls

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Existing backend endpoints

```text
/admin/export/orders.csv
/admin/export/orders.xlsx
/admin/export/products.csv
/admin/export/products.xlsx
/admin/export/report
```

### Required implementation

* visible export controls;
* correct file/download handling;
* supported date filters;
* loading states;
* error states;
* capability guards.

### Important

Do not wait for `F4.3`.

### Verification

Real browser download flow + typecheck/lint/build.

---

## AB-FE-05 — Admin products server pagination

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Required implementation

* server-side pagination;
* preserve filters/search between pages;
* reset page when filters change;
* display total/pages;
* loading state;
* eliminate whole-table loading.

### File collision

Shares `admin.products.tsx` with AB-FE-02.

### Verification

Network inspection + frontend checks.

---

## B3.11 — Contact-form spam guard

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** resolved D1

### Required implementation

Implement:

* PostgreSQL-backed per-IP throttle;
* maximum 5 submissions / 10 minutes / IP;
* honeypot field;
* safe response on abuse;
* no Redis;
* no CAPTCHA;
* no second rate-limit framework.

### Acceptance

* repeated automated submissions are throttled;
* legitimate contact form continues working;
* honeypot submissions are rejected;
* authenticated and guest requests are protected.

### Verification

Focused API abuse tests + live smoke.

---

## B2.1 — SMS/email notifications

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** resolved D2

### Provider architecture

```text
Business Event
      ↓
Notification Service
      ├── SMS Adapter → Kavenegar
      └── Email Adapter → SMTP
```

### Scope

Implement only:

* order created;
* payment confirmed;
* order shipped;
* order cancelled;
* refund approved/settled;
* password reset;
* preorder-related transactional notification where required.

### Requirements

* provider failures do not corrupt business transactions;
* notification retries are safe;
* repeated lifecycle transitions do not duplicate messages;
* credentials come from environment/config;
* business services do not call provider-specific SDKs directly.

### Verification

Provider adapter tests + idempotency/error-path tests + integration test with
mock/stub transport.

---

## F2.3 — Forgot password

* **Layer:** Full-stack
* **Status:** TODO
* **Dependencies:** B2.1 notification transport

### Required implementation

* reset token generation;
* secure token storage;
* expiration;
* one-time consumption;
* safe user enumeration behavior;
* reset email;
* reset endpoint;
* reset request UI;
* reset form UI.

### Verification

Focused auth tests + notification stub + frontend flow.

---

# P2 — Quality / scalability

## B5.1b — Audit-log DB tamper resistance

* **Layer:** Infra/DB
* **Status:** TODO
* **Dependencies:** none

### Required implementation

Make `audit_logs` append-only for the application role:

* INSERT allowed;
* SELECT allowed;
* UPDATE denied;
* DELETE denied.

### Verification

* clean DB bootstrap;
* negative UPDATE/DELETE checks;
* positive audit INSERT.

---

## AB-BE-01 — Inventory ledger

* **Layer:** Backend + DB
* **Status:** TODO
* **Dependencies:** B6.8

### Required implementation

Create:

```text
inventory_logs
```

with:

* `id`;
* `variant_id`;
* `change_amount`;
* `reason`;
* `created_by`;
* `created_at`.

Reasons:

```text
purchase
restock
return
manual_adjustment
```

### Rule

This must become the canonical inventory history.

Do not introduce a second inventory accounting mechanism.

### Acceptance

Every supported stock mutation generates one appropriate ledger event.

### Verification

Pytest + live stock mutation flow.

---

## AB-BE-02 — Variant SKU / price / color fields

* **Layer:** Backend + DB + API
* **Status:** TODO
* **Dependencies:** none
* **Blocks:** AB-FE-03

### Required implementation

Add/support:

* globally unique SKU;
* nullable `price_override`;
* `color_hex`;
* schemas;
* CRUD;
* idempotent DDL.

### Verification

Clean bootstrap + CRUD tests.

---

## F5.8 — Remove duplicate `/shop` catalog fetch

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Problem

`/shop` currently triggers both:

```text
catalogQuery
+
filtered products query
```

### Required implementation

Establish one canonical request path for each shop state.

### Acceptance

Normal, filtered and search visits must not issue unnecessary full-catalog requests.

### Verification

Network inspection + typecheck/lint/build.

---

## F5.7 — Admin chart bundle split

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** measurement first

### Required workflow

1. Measure the current production bundle.
2. Identify actual contributors.
3. Apply evidence-based route/code splitting.
4. Build again.
5. Compare before/after size.

### Important

Do not assume lodash is a direct dependency.

Do not remove dependencies blindly.

### Verification

Documented before/after bundle measurement + successful build.

---

## F4.3 — Reusable AdminDataTable

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** resolved D8

### Canonical library

```text
@tanstack/react-table
```

### Required implementation

* reusable table abstraction;
* search;
* filter chips;
* sorting;
* server-side pagination;
* bulk selection;
* bulk actions;
* copy helpers;
* shared toolbar;
* consistent loading/empty/error states.

### Important

Export controls remain independent in `AB-FE-02`.

### Verification

Use the component in multiple real admin screens.

---

## AB-FE-01 — Admin topbar completion

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Required implementation

Build on the existing F4.2 shell:

* breadcrumbs;
* staff profile/avatar actions;
* command/quick actions where appropriate;
* storefront preview link;
* responsive details.

### Do not

Rewrite `AdminLayout` or replace the existing role-gated shell.

### Verification

Desktop + mobile + multiple role scenarios.

---

## AB-FE-03 — Two-column product editor + RHF/Zod + swatches

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** AB-BE-02

### Required implementation

* two-column layout;
* React Hook Form;
* Zod schema;
* product details;
* variant matrix;
* SKU;
* color swatch;
* size;
* quantity;
* price override.

### Storage rule

Use the existing MinIO flow:

```text
POST /storage/upload-url
POST /storage/sign
```

Never direct Supabase storage.

### Verification

Create/edit + validation + persisted backend values.

---

## AB-FE-04 — Product image gallery manager

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Required implementation

* drag/drop;
* preview;
* reorder;
* primary image;
* delete;
* progress;
* retry/error handling.

### Canonical storage

```text
/storage/upload-url
/storage/sign
→ MinIO
```

### Verification

Real upload/reorder/delete flow on local Docker stack.

---

## F3.5b — Re-check cart stock on window focus

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** none

### Required implementation

When the cart window/tab receives focus:

```text
window focus
     ↓
stockCheck()
     ↓
refresh cart availability state
```

Checkout server-side validation remains the final authority.

### Verification

Simulate stale stock while the cart is open, then focus the window and verify
the UI updates.

---

## B2.5 — Webhooks + background jobs

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** B2.1 notification infrastructure

### Required implementation

* order events;
* background job mechanism;
* abandoned-payment reminders;
* notification integration;
* idempotent job execution;
* retry behavior.

### Verification

Worker execution + restart/retry test + duplicate-event test.

---

# P3 — Future

## B2.3 — PDF invoices

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** none

### Before coding

Confirm server-generated PDF is still required because F4.4 already provides
browser invoice printing.

### Verification

Generated PDF must contain correct order data and open correctly.

---

## F3.4b — Guest recently viewed

* **Layer:** Frontend
* **Status:** TODO
* **Dependencies:** resolved D7(c)

### Required behavior

* localStorage;
* maximum 8 product IDs/timestamps;
* dedupe;
* newest wins;
* merge with account history on sign-in.

### Verification

```text
guest browse
    ↓
localStorage
    ↓
sign in
    ↓
merge
    ↓
dedupe
    ↓
account recently-viewed
```

---

## AB-FE-06 — Customer 360° profile

* **Layer:** Full-stack/frontend
* **Status:** TODO
* **Dependencies:** none

### Required implementation

* customer overview;
* registration date;
* order history;
* saved addresses;
* wishlist;
* LTV;
* average days between purchases;
* role management entry point;
* customer tier.

### Tier rules

```text
New       = fewer than 3 delivered orders
VIP       = 3+ delivered orders
Wholesale = explicitly assigned by staff
```

Wholesale takes precedence over New/VIP.

If an explicit Wholesale representation does not yet exist in the backend,
add the minimum canonical customer-tier representation required by this task.

Do not create a second authorization role system.

### Verification

Data must match existing account/order/address/wishlist sources and obey admin
capabilities.

---

## F1.9 — Lovable preview tooling

* **Layer:** Frontend tooling
* **Status:** TODO
* **Priority:** P3
* **Dependencies:** none

Only implement if the tooling still provides value after the app is fully
independent of Lovable.

Do not reintroduce Lovable/Supabase architecture.

---

## B2.2a — CSV product import

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** resolved D3

### Required implementation

* idempotent upsert;
* `product_id` canonical key when provided;
* otherwise normalized `name + category`;
* only supplied columns update;
* duplicates inside one CSV rejected;
* validation/reporting;
* transactional boundaries;
* deterministic retry behavior.

### Verification

* insert new product;
* update existing by ID;
* update existing by normalized name/category;
* omitted fields remain unchanged;
* duplicate rows fail clearly;
* repeated import is idempotent.

---

## B4.13 — Preorder fulfilment flag

* **Layer:** Backend
* **Status:** TODO
* **Dependencies:** B2.1

### Required implementation

* preorder marker on order/item;
* allow checkout for `availability=preorder`;
* do not decrement physical inventory for preorder items;
* preserve existing order state machine;
* expose preorder information to admin;
* use `available_at` as fulfillment readiness information;
* integrate applicable notifications.

### Important

Do not create new order status strings.

### Verification

Test:

```text
preorder product
    ↓
checkout
    ↓
payment
    ↓
order marked preorder
    ↓
physical stock unchanged
    ↓
admin can identify item
```

Also test cancellation/refund behavior.

---

# 8. Explicitly not executable

## B4.8 — Product model dimension

**Status: DROPPED**

Reason:

Product variants remain permanently scoped to:

```text
Size × Color
```

No third dimension is required for the current roadmap.

Do not implement.

---

## B4.9 — Stock reservation with TTL

**Status: DROPPED**

Reason:

The current payment architecture does not justify reservation/TTL complexity.

Keep transactional stock decrement at order creation.

Do not implement.

---

## B2.6 — Coupon admin UI support

**Status: OBSOLETE**

Reason:

Superseded by the existing backend coupon system and `F4.5`.

Do not implement.

---

## Historical duplicate IDs

`B6.1` appears multiple times in `backend-tasks.md`, while `B6.3` overlaps the
order-lifecycle item.

Do not create another task because of these historical identifier collisions.

---

# 9. Dependency graph

```text
B6.8
└──→ AB-BE-01

AB-BE-02
└──→ AB-FE-03

B2.1
├──→ F2.3
├──→ B2.5
└──→ B4.13

F3.4b
└── guest localStorage → login merge

AB-FE-06
└── resolved customer tier rules

F4.3
└── @tanstack/react-table

B4.8
└── DROPPED

B4.9
└── DROPPED
```

---

# 10. Recommended execution batches

## Batch A — Critical backend

Run first:

```text
(empty — B6.8, B6.9 and AB-BE-03 are all DONE)
```

Batch A is complete. `AB-BE-01` is unblocked; execution moves to Batch B.

---

## Batch B — Admin frontend gaps

Can run in parallel with Batch A.

However, `AB-FE-02` and `AB-FE-05` should not modify
`admin.products.tsx` concurrently.

```text
F5.5
F5.6
AB-FE-02
AB-FE-05
```

---

## Batch C — Backend quality / infrastructure

```text
B5.1b
AB-BE-01
AB-BE-02
```

`AB-BE-01` begins after `B6.8`.

---

## Batch D — Frontend quality

```text
F5.8
F5.7
AB-FE-01
AB-FE-04
F3.5b
```

These can mostly run in parallel because they touch different concerns.

---

## Batch E — Product editor

```text
AB-FE-03
```

Start after `AB-BE-02`.

---

## Batch F — Resolved-decision work

These are no longer blocked, but some have task dependencies:

```text
B3.11
B2.1
F2.3
B2.5
B2.2a
B4.13
F3.4b
F4.3
AB-FE-06
```

Notification chain:

```text
B2.1
├──→ F2.3
├──→ B2.5
└──→ B4.13
```

---

## Batch G — P3

```text
B2.3
F1.9
```

These should not delay P0/P1/P2 work.

---

# 11. Master backlog count

After resolving the decisions:

### Remaining implementation units

**27**

### Ready for execution

**27**

### Blocked

**0**

### Dropped

**2**

```text
B4.8
B4.9
```

### Obsolete

**1**

```text
B2.6
```

### Product decisions open

**0**

D1–D9 are resolved.

---

# 12. Priority distribution

| Priority  | Remaining |
| --------- | --------: |
| P0        |         1 |
| P1        |         9 |
| P2        |        11 |
| P3        |         6 |
| **Total** |    **27** |

Priority is execution guidance, not permission to rewrite requirements.

---

# 13. Documentation synchronization

When a task reaches `DONE`, synchronize:

1. the relevant checkbox in `backend-tasks.md` or `frontend-tasks.md`;
2. `plan/session-log.md`;
3. a task audit in `plan/audit/`;
4. this Master Backlog;
5. affected README/FEATURES/roadmap/design documents where the task changes their claims.

Known documentation drift:

* `B6.10` is implemented but unticked.
* `B2.6` is obsolete but open.
* duplicate `B6.1` identifiers exist.
* old ADMIN specs contain Supabase/RLS/RPC mechanism wording.
* some completed backend features historically lacked frontend tracking.

Do not treat documentation cleanup as justification for unrelated code changes.

---

# 14. Frozen invariants

Agents must not alter these without an explicit new product decision:

### Order statuses

```text
pending
processing
shipped
delivered
cancelled
```

`cancelled` and `delivered` remain terminal according to the existing lifecycle rules.

Do not introduce statuses such as:

```text
paid
placed
approved
fulfilled
```

into the existing order state machine unless a future explicit decision says so.

### Money

Existing cart/pricing/money rules remain unchanged.

### Authorization

Backend authorization remains authoritative.

### Storage

Use MinIO through the existing storage endpoints.

### Frontend HTTP

`src/lib/api.ts` remains the frontend HTTP/data boundary.

### Architecture

Do not reintroduce:

* Supabase;
* Supabase Auth;
* Supabase Storage;
* RLS;
* Postgres RPC;
* `createServerFn`;
* duplicate API clients;
* duplicate auth/role systems.

---

# 15. Audit baseline

Primary audit:

```text
plan/audit/2026-09-22-full-backlog-audit.md
```

Important:

The audit itself did not execute tests in its own session.

Prior verification figures mentioned by that audit come from earlier audit files and
must not be described as freshly rerun.

In particular:

`B6.8` has since been implemented and verified in its own session
(see `plan/audit/2026-09-22-b68-variant-stock-restore.md`); the figures there
were freshly executed.

---

# 16. Current execution pointer

## START HERE

```text
F5.5
```

Batch A (`B6.8`, `B6.9`, `AB-BE-03`) is complete — audits
[B6.8](audit/2026-09-22-b68-variant-stock-restore.md),
[B6.9](audit/2026-09-22-b69-refund-exception-handling.md),
[AB-BE-03](audit/2026-09-22-abbe03-coupon-max-discount-cap.md). `F5.5` is the
highest-priority open task (P1, Batch B, no dependencies).

After `F5.5` is completed:

1. update this pointer;
2. update the task status;
3. link the new audit;
4. record the actual verification level;
5. identify the next highest-priority `TODO`.

The execution pointer must always identify a single concrete next task.

---

# 17. Agent selection rule

When an agent is asked:

> "What should I work on next?"

It must:

1. read this file;
2. parse the machine-readable task index;
3. find the first `TODO` according to priority and dependency order;
4. verify the task is still genuinely incomplete in the live codebase;
5. execute only that task;
6. follow Rules 0–15;
7. produce an audit;
8. update this file.

It must **not** select work by:

* old checkbox ordering;
* stale ADMIN wording;
* filename alone;
* spec wording that conflicts with the live repository;
* an unticked checkbox that is already implemented;
* a new feature discovered during reconnaissance.

---

# 18. Agent stop conditions

An agent must stop and report instead of improvising when:

* a supposedly TODO task is already implemented;
* the live contract contradicts this backlog;
* implementing the task would require changing a frozen invariant;
* a required external credential/secret is missing;
* the task requires a product decision not present in this file;
* a shared abstraction would need an unrelated refactor;
* a test would have to be weakened to pass.

The agent must convert newly discovered independent work into a separate backlog
item instead of silently absorbing it.

---

# 19. Definition of DONE

A task is `DONE` only when all applicable conditions are true:

```text
implementation exists
        +
contract is correct
        +
authorization is verified
        +
error paths are verified
        +
tests are passing
        +
clean-environment checks done where required
        +
audit file written
        +
task checkbox synchronized
        +
session-log updated
        +
Master Backlog updated
```

"Code exists" is not enough.

---

# 20. Reconciliation record

This Master Backlog was reconciled against:

* `plan/audit/2026-09-22-full-backlog-audit.md`
* `plan/backend-tasks.md`
* `plan/frontend-tasks.md`
* `plan/ADMIN-BACKEND_TASKS.md`
* `plan/ADMIN-FRONTEND_TASKS.md`

Reconciliation date:

**2026-09-22**

Current state:

```text
27 remaining implementation units
  (24 of the original 27, plus NEW-B68-1, NEW-B69-1 and NEW-ABBE03-1
   discovered during them)
3 completed implementation units (B6.8, B6.9, AB-BE-03)
0 blocked implementation units
2 dropped
1 obsolete
9 product decisions resolved
NEXT = F5.5
```
