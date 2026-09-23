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

**Implemented** (2026-09-22) in B3.11 exactly as above
([audit](audit/2026-09-22-b311-contact-spam-guard.md)): table
`contact_attempts`, per-IP advisory lock, generic Persian 429/400. The "per-IP"
key uses the shared client-IP resolver, which believes `X-Forwarded-For` only
from `TRUSTED_PROXIES`.

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

### Product adjustment (user, 2026-09-22 — B2.1 session)

No real Kavenegar or SMTP credentials exist yet. The decision is therefore
executed as:

* **Internal (in-app) notifications are fully implemented and active** — every
  transactional event above that has a live flow creates one notification for
  the customer, shown in the header bell and `/account/notifications`.
* **SMS infrastructure is implemented but disabled/unconfigured** until real
  Kavenegar credentials exist (`KAVENEGAR_API_KEY`, `KAVENEGAR_SENDER`).
* **Email infrastructure is implemented but disabled/unconfigured** until real
  SMTP configuration exists (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`, `SMTP_SSL`).
* **Admins switch SMS and email on/off independently** (`/admin/settings`,
  admin/super_admin; both default off). An external message is sent only when
  the switch is on **and** the provider is configured.
* **Internal notifications are not affected by those switches** — they have no
  switch at all.
* **Missing external credentials never fail a business transaction**, and
  neither does a provider error: sends happen after the commit from an outbox.
* **Real external provider activation happens later**, when real
  credentials/configuration are available — tracked as `B2.1a`.

**Unblocks:** `B2.1`, `F2.3`, `B2.5`, `B4.13`. (`B2.1` is DONE — see its section.)

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

`B2.1` is **DONE** (2026-09-22), so its dependents are released:

```text
B2.1 (DONE)
├──→ F2.3    — reset email goes through services/notifications.py (email-only entry point to add)
├──→ B2.5    — must add the pending/failed delivery sweeper
├──→ B4.13   — adds the preorder notification type
└──→ B2.1a   — real provider activation (needs credentials)
```

## Admin products file collision

`AB-FE-02` and `AB-FE-05` both modify
`admin.products.tsx`.

Execute them sequentially unless file ownership is explicitly separated.
`AB-FE-02` is DONE (2026-09-22) — it only added the export buttons to the page
header (`ProductsExportButtons`). `AB-FE-05` is DONE too (2026-09-22). Both
changes to the file shipped in sequence; the collision is closed.

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
    "agent_start_task": "B5.1d",
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
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "frontend-tasks.md",
      "scope": "Add typed API access and an authorized admin audit-log viewer with filters, pagination, old/new values, IP, loading, empty, and error states.",
      "audit": "plan/audit/2026-09-22-f55-audit-log-viewer.md",
      "verification_level": "browser tested",
      "completed": "2026-09-22"
    },
    {
      "id": "F5.6",
      "title": "Role management UI",
      "priority": "P1",
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "frontend-tasks.md",
      "scope": "Manage staff role sets from the users page using the canonical backend capability model.",
      "audit": "plan/audit/2026-09-22-f56-role-management-ui.md",
      "verification_level": "browser tested",
      "completed": "2026-09-22"
    },
    {
      "id": "AB-FE-02",
      "title": "Admin export controls",
      "priority": "P1",
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "ADMIN-FRONTEND_TASKS.md plus audit-derived task",
      "scope": "Expose existing order/product CSV/XLSX/report exports with correct download handling, filters, loading/error states, and capability guards.",
      "audit": "plan/audit/2026-09-22-abfe02-admin-export-controls.md",
      "verification_level": "browser tested",
      "completed": "2026-09-22"
    },
    {
      "id": "AB-FE-05",
      "title": "Admin products server pagination",
      "priority": "P1",
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "B",
      "source": "ADMIN-FRONTEND_TASKS.md plus audit-derived task",
      "scope": "Use server pagination for admin products, preserve filters, reset page when filters change, and stop full-table fetching.",
      "audit": "plan/audit/2026-09-22-abfe05-admin-products-pagination.md",
      "verification_level": "browser tested",
      "completed": "2026-09-22"
    },
    {
      "id": "B3.11",
      "title": "Contact-form spam guard",
      "priority": "P1",
      "status": "DONE",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Implement PostgreSQL-backed per-IP throttling at 5 requests per 10 minutes plus honeypot; no Redis or CAPTCHA.",
      "audit": "plan/audit/2026-09-22-b311-contact-spam-guard.md",
      "verification_level": "fully verified",
      "completed": "2026-09-22"
    },
    {
      "id": "B2.1",
      "title": "SMS/email notifications",
      "priority": "P1",
      "status": "DONE",
      "layer": "backend",
      "depends_on": [],
      "blocks": ["F2.3", "B2.5", "B4.13", "B2.1a"],
      "batch": "F",
      "source": "backend-tasks.md",
      "scope": "Canonical notification service: in-app notifications for every live D2 event (order created/paid/shipped/cancelled, refund approved/settled) deduplicated by UNIQUE(user_id, event_key) in the business transaction; admin SMS/email switches; Kavenegar/SMTP providers from env config behind an after-commit outbox; providers unconfigured (no real credentials).",
      "audit": "plan/audit/2026-09-22-b21-notification-infrastructure.md",
      "verification_level": "fully verified (in-app notifications, switches and provider layer up to the provider boundary); real SMS/email delivery unverified — no credentials (B2.1a)",
      "completed": "2026-09-22"
    },
    {
      "id": "B2.1a",
      "title": "Activate the real SMS/email providers",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend_infra",
      "depends_on": ["B2.1"],
      "blocks": [],
      "batch": "F",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-B21-1",
      "discovered_during": "B2.1",
      "scope": "Requires real Kavenegar + SMTP credentials (stop and report if absent). Put them in infra/.env, confirm *_configured on /admin/settings, send one real SMS and one real email end to end, verify sender line / TLS mode, record the result. Adapters were only tested against stub transports."
    },
    {
      "id": "F2.3",
      "title": "Forgot password",
      "priority": "P1",
      "status": "DONE",
      "layer": "fullstack",
      "depends_on": ["B2.1"],
      "blocks": [],
      "batch": "F",
      "source": "frontend-tasks.md",
      "scope": "Implement secure reset tokens, expiry, one-time use, email delivery, backend reset API, request UI, and reset UI.",
      "audit": "plan/audit/2026-09-23-f23-forgot-password.md",
      "verification_level": "fully verified (real reset-email delivery unverified — SMTP not configured, B2.1a)",
      "completed": "2026-09-23"
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
      "id": "F5.9",
      "title": "Coupon discount-cap field in the admin dialog",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": ["AB-BE-03"],
      "blocks": [],
      "batch": "B",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-ABBE03-1",
      "discovered_during": "AB-BE-03",
      "scope": "Expose coupons.max_discount_cap in the F4.5 admin coupon dialog (admin.coupons.tsx) and in the AdminCoupon / adminCreateCoupon / adminUpdateCoupon types in src/lib/api.ts, including the 0-clears-the-ceiling semantics on PATCH."
    },
    {
      "id": "B5.1c",
      "title": "Reject a malformed admin_id on GET /admin/audit-logs with 422, not 500",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-F55-1",
      "discovered_during": "F5.5",
      "scope": "Type the admin_id query parameter of routers/admin.py::audit_logs as UUID so ?admin_id=<not-a-uuid> returns 422 instead of reaching CAST(:admin_id AS uuid) and failing with 500; add an api_smoke/pytest error-path check."
    },
    {
      "id": "B5.4a",
      "title": "Role-change lockout guard",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-F56-1",
      "discovered_during": "F5.6",
      "scope": "PUT /admin/users/{id}/roles must reject (409) a caller removing their own users-capable role and the removal of the last holder of the users capability; add pytest coverage for both and for the allowed cases."
    },
    {
      "id": "F5.10",
      "title": "Hide staff nav tabs from non-staff in the admin shell",
      "priority": "P3",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-F56-2",
      "discovered_during": "F5.6",
      "scope": "admin.tsx falls back to ROLE_TAB_KEYS[\"support\"] for unknown roles, so a customer on /admin/* sees dashboard/messages/reviews tabs next to the no-access notice; render no tabs for non-staff roles."
    },
    {
      "id": "B2.2b",
      "title": "Export date/encoding correctness",
      "priority": "P3",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-ABFE02-1",
      "discovered_during": "AB-FE-02",
      "scope": "services/exports.py::parse_range must honour a supplied UTC offset (astimezone, naive stays UTC); add a UTF-8 BOM to the CSV exports for Excel; Persian 422 detail for bad dates; pytest for the offset case."
    },
    {
      "id": "B5.4b",
      "title": "include_inactive follows is_admin, not the catalog capability",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-ABFE05-1",
      "discovered_during": "AB-FE-05",
      "scope": "GET /products honours include_inactive only for admin/super_admin; gate it on has_capability(roles, \"catalog\") so order_manager sees and can re-activate inactive products in /admin/products; add a test."
    },
    {
      "id": "F5.11",
      "title": "/shop leaks invalid URL params to the API",
      "priority": "P3",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-ABFE05-2",
      "discovered_during": "AB-FE-05",
      "scope": "shop.tsx validateSearch omits rejected keys, so the router's merge over the parent's raw search passes ?page=abc / ?category=hack to GET /products (422 / wrong filter); return rejected keys as explicit undefined, as admin.products.tsx does."
    },
    {
      "id": "F5.12",
      "title": "Cart provider loads the whole catalogue on every route",
      "priority": "P2",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-ABFE05-3",
      "discovered_during": "AB-FE-05",
      "scope": "CartProvider in __root.tsx runs catalogQuery (all products, include_inactive=true) on every page incl. admin; fetch only the cart's products or defer until the cart is used. Related to F5.8."
    },
    {
      "id": "B5.1d",
      "title": "record_audit rolls back the mutation it audits",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-B21-2",
      "discovered_during": "B2.1",
      "scope": "services/audit.py::record_audit swallows an insert failure with session.rollback(), silently discarding the order/refund/role change on the same session while the router still returns 200. Use a SAVEPOINT around the audit insert or fail the request (decide), and add a pytest forcing the audit insert to fail."
    },
    {
      "id": "B6.13",
      "title": "Documented pytest -q silently skips every live-DB test",
      "priority": "P2",
      "status": "DONE",
      "layer": "backend_tests",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-B21-3",
      "discovered_during": "B2.1",
      "scope": "test_addresses.py and three other modules set a dummy DATABASE_URL at import; app.config.settings caches it, so every live-DB module skips (77 passed / 60 skipped instead of 137 passed). One conftest default (compose URL) or no app.config import before it; the AGENTS.md verification command must run the integration tests.",
      "audit": "plan/audit/2026-09-23-b613-pytest-runs-db-tests.md",
      "verification_level": "locally tested",
      "completed": "2026-09-23"
    },
    {
      "id": "F5.13",
      "title": "Guest direct-load of a protected route logs a hydration mismatch",
      "priority": "P3",
      "status": "TODO",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-B21-4",
      "discovered_during": "B2.1",
      "scope": "Signed out, opening an ssr:false _authenticated route (e.g. /account/payments) renders it on the server, then the client beforeLoad redirects to /auth and React reports a hydration mismatch page error. Pre-existing (identical without the notification bell). Redirect without a mismatching first render."
    },
    {
      "id": "F5.14",
      "title": "Admin coupon create / edit / toggle fail with 422 (text/plain body)",
      "priority": "P1",
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-B21-5",
      "discovered_during": "B2.1",
      "scope": "api.adminCreateCoupon / adminUpdateCoupon send body: JSON.stringify(...) without the JSON content type (request() sets it only for json:), so FastAPI rejects every coupon save and active toggle with 422. Pass json: in both; verify create, edit and toggle in a browser.",
      "audit": "plan/audit/2026-09-22-f514-coupon-json-body.md",
      "verification_level": "browser tested",
      "completed": "2026-09-22"
    },
    {
      "id": "F5.15",
      "title": "A failed /auth/me signs the user out",
      "priority": "P2",
      "status": "DONE",
      "layer": "frontend",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-B21-6",
      "discovered_during": "B2.1",
      "scope": "AuthProvider.refresh() clears the token on any api.me() error (network error, backend restart, request interrupted by a full-page navigation), not only 401/403. Clear only on 401/403; otherwise keep the token and retry.",
      "audit": "plan/audit/2026-09-23-f515-auth-refresh-keeps-session.md",
      "verification_level": "browser tested",
      "completed": "2026-09-23"
    },
    {
      "id": "F5.16",
      "title": "Coupon edit dialog cannot clear expiry / total cap / discount kind",
      "priority": "P2",
      "status": "TODO",
      "layer": "fullstack",
      "depends_on": [],
      "blocks": [],
      "batch": "D",
      "source": "frontend-tasks.md",
      "discovered_as": "NEW-F514-1",
      "discovered_during": "F5.14",
      "scope": "admin.coupons.tsx sends null for an emptied expiry / max_uses / the other discount kind; PATCH /coupons/{id} treats null as unchanged (expires_at clears only on \"\"; max_uses has no clear encoding). Define clear semantics in CouponUpdate, send them from the dialog, add pytest + browser checks."
    },
    {
      "id": "B6.14",
      "title": "A password reset does not end existing sessions",
      "priority": "P2",
      "status": "TODO",
      "layer": "backend",
      "depends_on": [],
      "blocks": [],
      "batch": "C",
      "source": "backend-tasks.md",
      "discovered_as": "NEW-F23-1",
      "discovered_during": "F2.3",
      "scope": "JWTs are stateless for 7 days, so a token stolen before a password reset keeps working after it. Add users.password_changed_at (or a token version) set by reset_password, and reject tokens whose iat predates it in get_current_user / get_optional_user; tests for both."
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
    "total_executable": 45,
    "done": 13,
    "open": 32,
    "P0": 0,
    "P1": 0,
    "P2": 19,
    "P3": 13,
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
* **Not delivered:** no admin UI field yet (`F5.9`, discovered as `NEW-ABBE03-1`); fixed
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
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Backend:** `GET /admin/audit-logs`
* **Audit:** [`plan/audit/2026-09-22-f55-audit-log-viewer.md`](audit/2026-09-22-f55-audit-log-viewer.md)
* **Verification level:** browser tested (tsc clean, lint 0 errors, build OK,
  35/35 headless-Chromium checks across anonymous / customer / support /
  order_manager / admin incl. direct URL + refresh, mocked 500/403 error states,
  375 px layout; backend regression pytest 70 passed, `api_smoke.py` 196/0)
* **Delivered:** `/admin/audit` (admin/super_admin tab, role notice for other
  staff on direct entry), `api.adminAuditLogs()` + `AuditLogEntry` type,
  action / entity / staff / entity-id filters, 25-row offset paging (limit 26
  probes for a next page — the endpoint has no total), Jalali timestamp with time
  (`formatFaDateTime`), IP, old→new value table, loading / empty / error states.
  Backend contract unchanged.
* **Discovered:** `B5.1c` (was `NEW-F55-1`) — malformed `admin_id` → 500.

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
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Backend:** `PUT /admin/users/{id}/roles`
* **Audit:** [`plan/audit/2026-09-22-f56-role-management-ui.md`](audit/2026-09-22-f56-role-management-ui.md)
* **Verification level:** browser tested (tsc clean, lint 0 errors, build OK,
  40/40 headless-Chromium + API checks: 401/403/403/403/422/404 authority matrix,
  page guards for anonymous/customer/support/order_manager, two-step grant and
  revoke, effect on the target's already-issued JWT, audit row, mocked 403/500,
  375 px; backend pytest 70 passed, `api_smoke.py` 196/0)
* **Delivered:** per-row «نقش‌ها» dialog in `/admin/users` (disabled on your own
  row). Step 1: `super_admin` / `order_manager` / `support` checkboxes with a
  capability summary, legacy roles read-only. Step 2: +/− diff and typed-email
  confirmation, then a full-set PUT. Invalidates the users + audit-log caches.
  `api.adminSetUserRoles()` + `StaffRole`. Backend unchanged.
* **Discovered:** `B5.4a` (was `NEW-F56-1`) — backend lockout guard;
  `F5.10` (was `NEW-F56-2`) — customers see staff nav tabs.

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

* **Layer:** Frontend (+ one backend CORS line)
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Audit:** [`plan/audit/2026-09-22-abfe02-admin-export-controls.md`](audit/2026-09-22-abfe02-admin-export-controls.md)
* **Verification level:** browser tested (45/45 headless-Chromium checks with
  real download events in `Asia/Tehran`: authority matrix, page guards,
  filename, file contents = direct API, inclusive local-day bounds, status
  filter, xlsx `PK`, loading + no double request, validation, 403/422/500/network
  errors, report parity + empty/error, fallback filename, 375 px; pytest 72
  passed incl. 2 new CORS tests, ruff clean, `api_smoke.py` 196/0, tsc/lint/build;
  F5.5/F5.6 suites re-run green through the refactored `request()`)
* **Delivered:**
  * `/admin/orders` panel: inclusive local date range + status → CSV/Excel,
    Jalali range preview, collapsible sales report from `/admin/export/report`.
  * `/admin/products` catalog CSV/Excel buttons.
  * `api.ts::requestFile()` (bearer token, RFC-6266 filename) sharing the token and
    error helpers extracted from `request()`, plus `exportRange()`, which sends
    local midnights as naive UTC with an exclusive `to`.
  * Backend: `expose_headers=["Content-Disposition"]` on CORS (the cross-origin
    download could not read the filename otherwise) + `tests/test_cors_expose.py`.
* **Discovered:** `B2.2b` (was `NEW-ABFE02-1`) — `parse_range` drops a supplied UTC
  offset; CSV lacks a UTF-8 BOM; English 422 detail.

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
* **Status:** DONE (2026-09-22)
* **Dependencies:** none
* **Audit:** [`plan/audit/2026-09-22-abfe05-admin-products-pagination.md`](audit/2026-09-22-abfe05-admin-products-pagination.md)
* **Verification level:** browser tested (36/36 headless-Chromium checks over 25
  throwaway fixture products, 45 total / 3 pages. Covered: paging, URL state,
  refresh, filters that survive paging and reset it, junk and out-of-range URLs,
  delete/edit/variant invalidation, dimmed placeholder, skeleton, error + retry,
  support guard, storefront unaffected, 375 px. Fixtures were removed afterwards.
  tsc/lint/build; pytest 72, `api_smoke.py` 196/0; F5.5/F5.6/AB-FE-02 suites
  re-run green)
* **Delivered:**
  * `/admin/products` reads 20-row pages of
    `GET /products?include_inactive=true` under `["admin-products"]` instead of
    the whole `["catalog"]`;
  * URL `?page=&category=&availability=`, server total, shared `Pager`;
  * skeleton, error and empty states; an out-of-range page goes to the last page;
  * save, delete and variant changes invalidate the list.
  * Also fixed on this route: TanStack's merge of validated over raw search
    leaked invalid params, so rejected keys are now returned as `undefined`.
* **Not eliminated:** one bare catalogue fetch still happens on every route
  (admin included). It comes from `CartProvider`, not this page, and is
  recorded as F5.12.
* **Discovered:**
  * `B5.4b` (was `NEW-ABFE05-1`) — `include_inactive` is gated on `is_admin`,
    not the catalog capability;
  * `F5.11` (was `NEW-ABFE05-2`) — `/shop` leaks invalid URL params;
  * `F5.12` (was `NEW-ABFE05-3`) — `CartProvider` loads the whole catalogue
    everywhere.

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

* **Layer:** Backend (+ DB, config, honeypot field in the contact form)
* **Status:** DONE (2026-09-22)
* **Dependencies:** resolved D1
* **Audit:** [`plan/audit/2026-09-22-b311-contact-spam-guard.md`](audit/2026-09-22-b311-contact-spam-guard.md)
* **Verification level:** fully verified.
  * 20 new tests; mutation checks show each mechanism (lock, commit-before-raise,
    trusted-proxy check, honeypot) turns its tests red.
  * pytest 92 passed, ruff clean, `api_smoke.py` 199/0.
  * Live curl: rotating spoofed XFF → `201×5, 429×2`, and the audit IP can no
    longer be spoofed.
  * Browser `/contact` 10/10 ×6.
  * Clean environment: `down -v` → `db-init` exit 0 through all four stages,
    `/health` OK, table and indexes on the fresh DB.
* **Delivered:**
  * `contact_attempts` + `services/contact_guard.py` (5 per 10 min per IP; all
    outcomes count; per-IP advisory lock);
  * honeypot `website` → 400; throttle → 429 (both generic Persian);
  * the form's hidden honeypot and a Persian 429 toast;
  * **the shared client-IP resolver was fixed in place**
    (`services/client_ip.py`): it previously trusted any caller's
    `X-Forwarded-For`, which would have made the limit and the audit IPs
    spoofable;
  * `TRUSTED_PROXIES` / `CONTACT_RATE_LIMIT` / `CONTACT_RATE_WINDOW_SECONDS`
    config.

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

* **Layer:** Backend (+ DB, config, frontend notification centre and admin settings)
* **Status:** DONE (2026-09-22) — executed as **notification infrastructure** per
  the D2 product adjustment (no real credentials)
* **Dependencies:** resolved D2
* **Audit:** [`plan/audit/2026-09-22-b21-notification-infrastructure.md`](audit/2026-09-22-b21-notification-infrastructure.md)
* **Verification level:** fully verified — for the in-app system, the
  switches and the provider layer up to the provider boundary. **Real SMS/email
  delivery is not verified** (no credentials; adapters tested against stub
  transports only) → `B2.1a`.
  * 45 new tests (`tests/test_notifications.py`); mutation checks turn them red
    for broken dedup, an ignored switch, re-sent `sent` rows and a missing hook.
  * pytest 137 passed (live DB), ruff clean, `api_smoke.py` 224/0.
  * Browser: B2.1 suite 58/58 (three consecutive dev-stack runs and again on the clean stack); role/route regression sweep 52/54 on the clean stack — both failures pre-existing and unrelated (F5.14, F5.15), each confirmed with the bell removed or by curl.
  * Clean environment: `down -v` → `db-init` exit 0 through all four stages,
    `/health` OK, tables/constraints/indexes and the settings row on the fresh DB.
* **Delivered:**
  * `services/notifications.py` — the one entry point (`notify_order_event`,
    `notify_refund_event`, `notify`); `notifications` rows written on the
    business session (commit/rollback together), deduplicated by
    `UNIQUE (user_id, event_key)`;
  * hooks at the live lifecycle points: checkout (created), gateway verify +
    simulator + staff `payment_status=paid` (paid), staff PATCH to `shipped`
    (with tracking code), `cancel_order_tx` (both cancel paths), refund
    `approved` / `refunded` (settled);
  * `notification_deliveries` outbox + after-commit background dispatch; a
    missing or failing provider never touches the business transaction;
    re-dispatch is retry-safe;
  * `KavenegarSmsProvider` / `SmtpEmailProvider` from env config only — both
    unconfigured, nothing is sent;
  * `notification_settings` + `GET/PATCH /admin/settings/notifications`
    (new `settings` capability = admin/super_admin; audited); SMS/email default off;
  * inbox API `GET /notifications` (envelope), `/notifications/unread-count`,
    `PATCH /notifications/{id}/read`, `POST /notifications/read-all`;
  * UI: header bell, `/account/notifications`, `/admin/settings`; the shared
    `ui/switch.tsx` RTL thumb bug fixed in place.
* **Not in this task:** password-reset and preorder hooks (no such flows — F2.3,
  B4.13), the retry sweeper (B2.5), real provider activation (B2.1a), ops alerts
  and non-D2 events.

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
* **Status:** DONE (2026-09-23)
* **Audit:** [`plan/audit/2026-09-23-f23-forgot-password.md`](audit/2026-09-23-f23-forgot-password.md)
* **Verification level:** fully verified — 14 new tests (mutation-checked),
  pytest 151, smoke 229/0, browser 20/20 (incl. a full UI reset + login with the
  new password), clean environment. Real email delivery is **not** verified (SMTP
  unconfigured, B2.1a); no dev shortcut exposes the link. Found on the way: `B6.14`.
* **Delivered:** `password_reset_tokens` (SHA-256 only, 30-min expiry, one-time,
  superseded by a newer link, ≤3 links/account/hour); `POST /auth/password/forgot`
  (identical 202 for every address) and `POST /auth/password/reset` (400 for a bad
  link); the email goes through `notifications.queue_private_email` (email switch +
  SMTP, after COMMIT, body never persisted); `/forgot-password`, `/reset-password`
  and the «رمز عبور را فراموش کرده‌اید؟» link on `/auth`.
* **Dependencies:** B2.1 notification transport (DONE)
* **B2.1 hand-off:** send the reset email through
  `backend/app/services/notifications.py` — add an **email-only** entry point there
  (a reset has no in-app notification); never call `SmtpEmailProvider` directly.
  SMTP is **unconfigured** (B2.1a), so first decide how the reset link is verified
  without real delivery (stub transport in tests; ask the user about dev/local
  behaviour — e.g. logging the link — before inventing one). Stop condition §18
  applies if real delivery is required.

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

## F5.14 — Admin coupon create / edit / toggle fail with 422

* **Layer:** Frontend
* **Status:** DONE (2026-09-22)
* **Audit:** [`plan/audit/2026-09-22-f514-coupon-json-body.md`](audit/2026-09-22-f514-coupon-json-body.md)
* **Verification level:** browser tested — headless Chromium 14/14 on
  `/admin/coupons` (create, toggle off/on, edit, delete, duplicate-code and
  empty-discount errors; every write sent as `application/json`); tsc / lint /
  build clean. Fix: `json:` instead of a raw `body:` in `api.adminCreateCoupon` /
  `api.adminUpdateCoupon`. Found on the way: `F5.16`.
* **Priority:** P1
* **Batch:** D
* **Dependencies:** none
* **Discovered as:** `NEW-B21-5` during `B2.1` (browser regression sweep) —
  legacy discovery ID only; `F5.14` is the executable ID.
* **Source:** `frontend-tasks.md` F5.14

### Problem

`api.adminCreateCoupon` and `api.adminUpdateCoupon` in `src/lib/api.ts` pass
`body: JSON.stringify(…)`; `request()` sets `Content-Type: application/json`
only when called with `json:`. The browser therefore sends `text/plain` and
FastAPI 0.141 rejects the body with 422 («Input should be a valid dictionary or
object…»). Verified with curl: the identical body is 200 as `application/json`,
422 as `text/plain`. Every coupon create, edit and «فعال» toggle on
`/admin/coupons` fails today — a shipped feature (F4.5) is broken.

### Required implementation

Use `json:` in both methods (no change to `request()`, the backend or the
payload shape); keep `F5.9`'s future `max_discount_cap` field in mind.

### Verification

Browser: create, edit and toggle a coupon → 200 and the UI reflects it;
`bun run lint` / `tsc` / `build`.

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
* **Dependencies:** B2.1 notification infrastructure (DONE)
* **B2.1 hand-off:** add the sweeper for `notification_deliveries` — re-dispatch
  rows left `pending` by a crash and retry `failed` ones with a cap, by calling
  `services/notifications.dispatch_deliveries()` (already retry-safe: it only
  picks `pending`/`failed` rows under a row lock).

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

## F5.9 — Coupon discount-cap field in the admin dialog

* **Layer:** Frontend
* **Status:** TODO
* **Priority:** P2
* **Batch:** B
* **Dependencies:** `AB-BE-03` (DONE)
* **Discovered as:** `NEW-ABBE03-1` during `AB-BE-03` — legacy discovery ID
  only; `F5.9` is the executable ID.
* **Source:** `frontend-tasks.md` F5.9

### Problem

The backend stores and enforces `coupons.max_discount_cap`, but
`admin.coupons.tsx` and the `AdminCoupon` / `adminCreateCoupon` /
`adminUpdateCoupon` types in `src/lib/api.ts` do not mention it, so a ceiling
can only be set through the API.

### Required implementation

* add `max_discount_cap` to the coupon types in `src/lib/api.ts`;
* add the field to the F4.5 coupon dialog (create + edit) and show it in the list;
* on edit, sending `0` clears the ceiling (backend `PATCH` semantics);
* the field is meaningful for percent-off coupons only; the backend stays the
  authority for the discount value.

### Verification

Typecheck + lint + build + create/edit/clear flow against a running stack.

---

## B5.1d — `record_audit` rolls back the mutation it audits

* **Layer:** Backend
* **Status:** TODO
* **Priority:** P2
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-B21-2` during `B2.1` — legacy discovery ID only;
  `B5.1d` is the executable ID.
* **Source:** `backend-tasks.md` B5.1d

### Problem

`services/audit.py::record_audit` catches an insert failure, calls
`session.rollback()` and logs. The rollback also discards the order-status /
refund / role / coupon change made earlier on the same session; the router then
commits an empty transaction and still answers 200 with the new values — a
silent lost update. Only reachable when the audit insert itself fails.

### Required implementation

Decide (and document) one behaviour: either isolate the audit insert in a
SAVEPOINT (`begin_nested()`) so a failed audit row no longer undoes the mutation,
or let the failure fail the request. Do not swallow-and-rollback.

### Verification

A pytest that forces the audit insert to fail and asserts the chosen outcome on
the mutation; full pytest + ruff + `api_smoke.py`.

---

## F5.16 — Coupon edit dialog cannot clear expiry / total cap / discount kind

* **Layer:** Full-stack
* **Status:** TODO
* **Priority:** P2
* **Batch:** D
* **Dependencies:** none (touches the same dialog as `F5.9`)
* **Discovered as:** `NEW-F514-1` during `F5.14` — legacy discovery ID only;
  `F5.16` is the executable ID.
* **Source:** `frontend-tasks.md` F5.16

### Problem

`admin.coupons.tsx` builds the edit PATCH with `null` for every emptied field
(expiry, total cap, the discount kind not chosen). `PATCH /coupons/{id}` treats
`null` as "leave unchanged": clearing the expiry and saving keeps the old date
(observed in the browser), a percent coupon switched to a fixed amount keeps its
`percent_off`, and `max_uses` has no "clear" encoding at all.

### Required implementation

Define explicit clear semantics in `CouponUpdate` (e.g. `""`/`0` like the
existing `expires_at` / `max_discount_cap` conventions), send them from the
dialog, and keep create unchanged.

### Verification

pytest for each clear path + a browser edit that clears expiry, cap and switches
kind.

---

## F5.15 — A failed `/auth/me` signs the user out

* **Layer:** Frontend
* **Status:** DONE (2026-09-23)
* **Audit:** [`plan/audit/2026-09-23-f515-auth-refresh-keeps-session.md`](audit/2026-09-23-f515-auth-refresh-keeps-session.md)
* **Verification level:** browser tested — 16/16; the same suite against the old
  `auth.tsx` fails the 4 transient-error checks (negative control). `refresh()`
  now clears the token only on 401/403/404 and otherwise keeps it and retries
  (1 s / 3 s / 10 s).
* **Priority:** P2
* **Batch:** D
* **Dependencies:** none
* **Discovered as:** `NEW-B21-6` during `B2.1` — legacy discovery ID only;
  `F5.15` is the executable ID.
* **Source:** `frontend-tasks.md` F5.15

### Problem

`src/lib/auth.tsx::AuthProvider.refresh()` calls `setToken(null)` whenever
`api.me()` throws — including a network error, a backend restart, or a request
interrupted by a full-page navigation — not only when the token is invalid.
Reproduced: a customer loading `/`, `/shop`, `/cart`, `/contact` in quick
succession loses the stored token and is sent to `/auth`; identical with the B2.1
notification bell removed (pre-existing).

### Required implementation

Clear the token only for 401/403 (`ApiError.status`); on other failures keep
it, stay "loading"/signed-out for this render and retry.

### Verification

Browser: interrupted `/auth/me` and a stopped backend keep the token; an
invalid/expired token still signs out.

---

## B6.14 — A password reset does not end existing sessions

* **Layer:** Backend (auth)
* **Status:** TODO
* **Priority:** P2
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-F23-1` during `F2.3` — legacy discovery ID only;
  `B6.14` is the executable ID.
* **Source:** `backend-tasks.md` B6.14

### Problem

Access tokens are stateless HS256 JWTs valid for 7 days. `reset_password` changes
the hash but nothing invalidates tokens issued before it, so an attacker holding a
stolen token keeps access after the victim resets — the reset does not recover the
account.

### Required implementation

Record `password_changed_at` (or a token version) on the user when the password
changes (reset — and any future change-password endpoint) and reject tokens whose
`iat` is older in `get_current_user` / `get_optional_user`. Keep the existing
role-from-DB resolution unchanged.

### Verification

pytest: a token issued before a reset → 401 afterwards; a token issued after → 200;
login still works. Smoke + clean environment (DDL).

---

## B6.13 — Documented `pytest -q` silently skips every live-DB test

* **Layer:** Backend tests
* **Status:** DONE (2026-09-23)
* **Audit:** [`plan/audit/2026-09-23-b613-pytest-runs-db-tests.md`](audit/2026-09-23-b613-pytest-runs-db-tests.md)
* **Verification level:** locally tested — the documented command went from
  79 passed / 72 skipped to **151 passed / 0 skipped**; with no database it still
  skips cleanly. One `tests/conftest.py` default; the four dummy URLs removed.
* **Priority:** P2
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-B21-3` during `B2.1` — legacy discovery ID only;
  `B6.13` is the executable ID.
* **Source:** `backend-tasks.md` B6.13

### Problem

`test_addresses.py` (collected first), `test_availability_and_filters.py`,
`test_pricing_and_coupons.py` and `test_variants.py` do
`os.environ.setdefault("DATABASE_URL", "…u:p@localhost:5432/db")` at import.
`app.config.settings` is cached from that, so every live-DB module then skips as
"no database reachable". The command in `AGENTS.md` / Rule 13 reports
**77 passed, 60 skipped**; with `DATABASE_URL` exported it is **137 passed**.
A green run of the documented command therefore proves nothing about the
integration tests.

### Required implementation

One default for the test session (e.g. a `conftest.py` setting the compose URL
before any `app` import), remove the per-module dummy URLs, and keep the
"skip when no database" behaviour for machines without the stack.

### Verification

`./.venv/bin/python -m pytest -q` with no env vars runs the live-DB tests
against the compose stack (0 skipped when it is up) and still skips cleanly when
it is down.

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
* **Dependencies:** B2.1 (DONE)
* **B2.1 hand-off:** add the preorder type to `TYPES` in
  `services/notifications.py` and fire it from the preorder lifecycle point with an
  `order:<id>:…` event key (the dedup mechanism).

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

## B5.1c — Malformed `admin_id` on the audit-log endpoint

* **Layer:** Backend
* **Status:** TODO
* **Priority:** P3
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-F55-1` during `F5.5` — legacy discovery ID only;
  `B5.1c` is the executable ID.
* **Source:** `backend-tasks.md` B5.1c

### Problem

`GET /admin/audit-logs?admin_id=foo` returns 500: the string reaches
`CAST(:admin_id AS uuid)` and Postgres raises. Admin-only caller; the F5.5 viewer
only sends real UUIDs.

### Required implementation

Type `admin_id` as `UUID | None` in `routers/admin.py::audit_logs` so FastAPI
answers 422; keep every other filter and the response shape unchanged.

### Verification

Error-path check (malformed → 422, valid UUID → 200) in `api_smoke.py` or pytest;
full pytest + ruff.

---

## B5.4a — Role-change lockout guard

* **Layer:** Backend
* **Status:** TODO
* **Priority:** P2
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-F56-1` during `F5.6` — legacy discovery ID only;
  `B5.4a` is the executable ID.
* **Source:** `backend-tasks.md` B5.4a

### Problem

`PUT /admin/users/{id}/roles` accepts a caller removing their own role and the
removal of the last `super_admin`; if no account keeps the `users` capability,
roles can only be repaired in the database. The F5.6 UI disables your own row,
but that is not authorization.

### Required implementation

Reject with 409 (Persian detail) when the caller would remove their own
users-capable role, or when the change would leave no account holding the
`users` capability; keep the contract otherwise unchanged.

### Verification

pytest for self-demotion, last-holder removal and the allowed cases; `api_smoke.py`;
ruff.

---

## F5.10 — Hide staff nav tabs from non-staff in the admin shell

* **Layer:** Frontend
* **Status:** TODO
* **Priority:** P3
* **Batch:** D
* **Dependencies:** none
* **Discovered as:** `NEW-F56-2` during `F5.6` — legacy discovery ID only;
  `F5.10` is the executable ID.
* **Source:** `frontend-tasks.md` F5.10

### Problem

A signed-in customer on `/admin/*` sees the "no admin access" notice, but the
sidebar still lists داشبورد / پیام‌ها / نظرات: `admin.tsx` falls back to
`ROLE_TAB_KEYS["support"]` for any unknown role. No data leaks (every call is
gated).

### Required implementation

Render no admin tabs for non-staff roles; keep the staff role → tab mapping as-is.

### Verification

Typecheck + lint + build; browser check as customer and as each staff role.

---

## B2.2b — Export date/encoding correctness

* **Layer:** Backend
* **Status:** TODO
* **Priority:** P3
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-ABFE02-1` during `AB-FE-02` — legacy discovery ID only;
  `B2.2b` is the executable ID.
* **Source:** `backend-tasks.md` B2.2b

### Problem

* `services/exports.py::parse_range` calls `.replace(tzinfo=UTC)`, so an explicit
  offset is dropped: `from=2026-09-22T00:00:00+03:30` is read as UTC midnight.
* CSV exports have no UTF-8 BOM, so Excel may garble Persian text when the `.csv`
  is opened directly.
* A bad date returns an English 422 detail.

The AB-FE-02 UI already sends offset-less UTC bounds and validates dates, so it is
unaffected.

### Required implementation

* Convert aware inputs with `astimezone(UTC)`; keep naive input as UTC (the UI's
  format).
* Prefix CSV bodies with a BOM.
* Persian 422 detail.
* Keep the exclusive `to` and every other contract detail.

### Verification

pytest for naive/offset/inverted ranges and the BOM; `api_smoke.py`; re-run the
AB-FE-02 browser flow.

---

## B5.4b — `include_inactive` follows `is_admin`, not the `catalog` capability

* **Layer:** Backend
* **Status:** TODO
* **Priority:** P2
* **Batch:** C
* **Dependencies:** none
* **Discovered as:** `NEW-ABFE05-1` during `AB-FE-05` — legacy discovery ID only.
* **Source:** `backend-tasks.md` B5.4b

### Problem

`GET /products?include_inactive=true` returns inactive rows only for
admin/super_admin (`AuthUser.is_admin`). `order_manager` holds the `catalog`
capability, so it may edit products, but it never sees inactive products in
`/admin/products` and cannot re-activate them. Measured: 39 of 44 rows are
visible to order_manager.

### Required implementation

Gate `include_inactive` on `has_capability(user.roles, "catalog")`; everything else
unchanged.

### Verification

pytest for anonymous / customer / support / order_manager / admin, `api_smoke.py`,
and a browser re-run of the AB-FE-05 script as order_manager.

---

## F5.11 — `/shop` leaks invalid URL params to the API

* **Layer:** Frontend
* **Status:** TODO
* **Priority:** P3
* **Batch:** D
* **Dependencies:** none
* **Discovered as:** `NEW-ABFE05-2` during `AB-FE-05` — legacy discovery ID only.
* **Source:** `frontend-tasks.md` F5.11

### Problem

TanStack Router merges a route's validated search over the parent's raw one, so
keys that `shop.tsx`'s `validateSearch` omits survive raw. `/shop?page=abc` sends
`page=abc` (422, retried 3×, no products), and `?category=hack` filters on it.

### Required implementation

Return rejected keys as explicit `undefined` (the pattern in
`admin.products.tsx`); keep every valid param unchanged.

### Verification

Browser: junk params → canonical URL and a valid request; existing shop filters
unaffected.

---

## F5.12 — Cart provider loads the whole catalogue on every route

* **Layer:** Frontend
* **Status:** TODO
* **Priority:** P2
* **Batch:** D
* **Dependencies:** none (related to `F5.8`)
* **Discovered as:** `NEW-ABFE05-3` during `AB-FE-05` — legacy discovery ID only.
* **Source:** `frontend-tasks.md` F5.12

### Problem

`CartProvider` in `__root.tsx` runs `catalogQuery` (every product,
`include_inactive=true`) on every page, admin pages included, to price and
stock-check the cart. It fires 1× on `/admin/products` and 1× on `/admin/orders`
alike.

### Required implementation

Load only what the cart needs (its product ids) or defer until the cart is used,
without changing cart money/stock rules (the backend stays authoritative at
checkout).

### Verification

Network inspection on storefront and admin routes; cart, checkout and
stock-issue flows re-tested.

---

## B2.1a — Activate the real SMS/email providers

* **Layer:** Backend / infra configuration
* **Status:** TODO
* **Priority:** P3
* **Batch:** F
* **Dependencies:** `B2.1` (DONE) + **real credentials from the user**
* **Discovered as:** `NEW-B21-1` during `B2.1` — legacy discovery ID only;
  `B2.1a` is the executable ID.
* **Source:** `backend-tasks.md` B2.1a

### Required implementation

* obtain real Kavenegar and SMTP credentials — **stop and report if they are
  missing** (§18); never invent or commit them;
* set them in `infra/.env` (or the deployment secret store) and recreate the
  backend; confirm `sms_configured` / `email_configured` on `/admin/settings`;
* switch the channels on, send one real SMS and one real email end to end,
  check the Kavenegar sender line / template rules and the SMTP TLS mode;
* fix any adapter mismatch found against the live service (the adapters were
  only tested against stub transports).

### Verification

A real delivery per channel, recorded in the audit with the delivery rows'
`status = sent`; a failing credential produces `failed` + `last_error` without
affecting the order.

---

## F5.13 — Guest direct-load of a protected route logs a hydration mismatch

* **Layer:** Frontend
* **Status:** TODO
* **Priority:** P3
* **Batch:** D
* **Dependencies:** none
* **Discovered as:** `NEW-B21-4` during `B2.1` — legacy discovery ID only;
  `F5.13` is the executable ID.
* **Source:** `frontend-tasks.md` F5.13

### Problem

Signed out, opening an `ssr: false` route under `_authenticated` (e.g.
`/account/payments`) renders it on the server; the client `beforeLoad` then
redirects to `/auth?redirect=…` and React reports «Hydration failed … server
rendered HTML didn't match the client». Nothing breaks visibly (the tree is
regenerated), but it is a page error on every such visit. Pre-existing — the
same with the B2.1 notification bell removed.

### Required implementation

Redirect without a mismatching first render (e.g. a server-side redirect for the
signed-out case, or a client-only shell that matches the server HTML).

### Verification

Headless browser: guest direct-load of `/account`, `/account/orders`,
`/account/payments` → `/auth?redirect=…` with no page error.

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

AB-BE-03 (DONE)
└──→ F5.9

AB-BE-02
└──→ AB-FE-03

B2.1 (DONE)
├──→ F2.3
├──→ B2.5
├──→ B4.13
└──→ B2.1a (also needs real credentials)

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
F5.5   (DONE 2026-09-22)
F5.6   (DONE 2026-09-22)
AB-FE-02 (DONE 2026-09-22)
AB-FE-05 (DONE 2026-09-22)
F5.9
```

`F5.9` depends on `AB-BE-03` (DONE) and edits `admin.coupons.tsx` plus the
coupon types in `src/lib/api.ts`; it does not collide with the other Batch B
files.

---

## Batch C — Backend quality / infrastructure

```text
B5.1b
AB-BE-01
AB-BE-02
B5.1c
B5.4a
B2.2b
B5.4b
B5.1d
B6.13  (DONE 2026-09-23)
B6.14
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
F5.10
F5.11
F5.12
F5.13
F5.14  (DONE 2026-09-22)
F5.15  (DONE 2026-09-23)
F5.16
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
B3.11  (DONE 2026-09-22)
B2.1   (DONE 2026-09-22)
F2.3   (DONE 2026-09-23)
B2.5
B2.2a
B4.13
B2.1a  (needs real credentials)
F3.4b
F4.3
AB-FE-06
```

Notification chain:

```text
B2.1 (DONE)
├──→ F2.3
├──→ B2.5
├──→ B4.13
└──→ B2.1a
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

**32** (13 completed: B6.8, B6.9, AB-BE-03, F5.5, F5.6, AB-FE-02, AB-FE-05, B3.11,
B2.1, F5.14, F2.3, F5.15, B6.13; 18 added by discovery: NEW-B68-1, NEW-B69-1, F5.9, B5.1c, B5.4a,
F5.10, B2.2b, B5.4b, F5.11, F5.12, B2.1a, B5.1d, B6.13, F5.13, F5.14, F5.15, F5.16,
B6.14)

### Ready for execution

**32** (`B2.1a` additionally needs real provider credentials from the user)

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
| P0        |         0 |
| P1        |         0 |
| P2        |        19 |
| P3        |        13 |
| **Total** |    **32** |

Recomputed from the JSON index on 2026-09-23 (B6.13).

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
B5.1d
```

Batch A (`B6.8`, `B6.9`, `AB-BE-03`) is complete — audits
[B6.8](audit/2026-09-22-b68-variant-stock-restore.md),
[B6.9](audit/2026-09-22-b69-refund-exception-handling.md),
[AB-BE-03](audit/2026-09-22-abbe03-coupon-max-discount-cap.md) — and so is every P1 in Batch B:
`F5.5` ([audit](audit/2026-09-22-f55-audit-log-viewer.md)), `F5.6`
([audit](audit/2026-09-22-f56-role-management-ui.md)), `AB-FE-02`
([audit](audit/2026-09-22-abfe02-admin-export-controls.md)) and `AB-FE-05`
([audit](audit/2026-09-22-abfe05-admin-products-pagination.md)). Batch B keeps
only `F5.9` (P2).

`B3.11` is DONE ([audit](audit/2026-09-22-b311-contact-spam-guard.md)), and so is
`B2.1` ([audit](audit/2026-09-22-b21-notification-infrastructure.md)) — executed as notification infrastructure under the D2
product adjustment: in-app notifications live, SMS/email built but unconfigured.

`F5.14` is DONE ([audit](audit/2026-09-22-f514-coupon-json-body.md)) and so is
`F2.3` ([audit](audit/2026-09-23-f23-forgot-password.md)) — **no P1 remains**.

`F5.15` is DONE ([audit](audit/2026-09-23-f515-auth-refresh-keeps-session.md)).

`B6.13` is DONE ([audit](audit/2026-09-23-b613-pytest-runs-db-tests.md)) — `pytest -q` now runs the live-DB tests.

The user asked for this run back to back: `F5.15` (DONE) → `B6.13` (DONE) →
`B5.1d` → `B2.1a` → `F5.13`. **`B5.1d`** (`record_audit` rolls back the mutation it
audits; P2, Batch C) is next. `B2.1a` will hit its stop condition (no real credentials) —
report it, do not fake it.

After each task: update this pointer, the task status, the audit link and the
verification level, and name the next task.

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
32 remaining implementation units
  (17 of the original 27, plus NEW-B68-1, NEW-B69-1, F5.9, B5.1c, B5.4a, F5.10,
   B2.2b, B5.4b, F5.11, F5.12, B2.1a, B5.1d, F5.13, F5.16 and B6.14 —
   the last thirteen discovered as NEW-ABBE03-1, NEW-F55-1, NEW-F56-1,
   NEW-F56-2, NEW-ABFE02-1, NEW-ABFE05-1/2/3, NEW-B21-1…4/6, NEW-F514-1 and
   NEW-F23-1 — found during them)
13 completed implementation units (B6.8, B6.9, AB-BE-03, F5.5, F5.6, AB-FE-02,
  AB-FE-05, B3.11, B2.1, F5.14, F2.3, F5.15, B6.13 — F5.14, F5.15 and B6.13
  themselves discovered as NEW-B21-5, NEW-B21-6 and NEW-B21-3)
0 blocked implementation units
2 dropped
1 obsolete
9 product decisions resolved
NEXT = B5.1d
```
