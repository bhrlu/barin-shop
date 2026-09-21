# Audit — 2026-09-21 — B5.1 admin audit log (spec BE-04)

## Task

**B5.1** from `plan/backend-tasks.md`: an `audit_logs` table plus writes on
privileged mutations (order status changes, refund resolution, product
price/stock changes, role changes) with admin id, old/new values and IP, and an
admin-only read endpoint — implementing spec **[BE-04]**'s audit-log half.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before starting ([BE-04] re-verified
against the implementation).

- **Followed:** [BE-04] table shape — `admin_id` (FK → users), `action`
  (`update_order_status`, `product_price_change`-style verbs),
  `entity_type` (`order`/`product`/…), `entity_id`, `old_values`/`new_values`
  (JSONB), `ip_address` (nullable), `created_at`. Role changes are not audited
  because granular roles (**B5.4**) do not exist yet — the only role mutation
  is manual seeding.
- **Deliberately ignored / adapted:**
  - **IP capture is plumbed but always NULL** — routers don't receive the
    request object today, and threading `Request` through every dependency for
    a field the store doesn't use yet is churn. The column exists; a follow-up
    can populate it (noted as a new checkbox, see task list).
  - **Spec's "roles stay in their own table" rule** — untouched; this task adds
    no role storage.
  - Tamper-resistance: the spec says "tamper-resistant trail". Postgres-level
    protections (REVOKE UPDATE/DELETE, append-only role) are infra work and NOT
    done — any SQL-privileged process can still edit rows. Recorded as open.

## What was done

**Schema (`AUDIT_DDL` in `app/db.py`, idempotent):**

- `audit_logs(id, admin_id → users ON DELETE SET NULL, action, entity_type,
  entity_id, old_values JSONB, new_values JSONB, ip_address, created_at)` with
  `created_at DESC` and `(entity_type, entity_id)` indexes.

**Service (`app/services/audit.py`):**

- `record_audit(session, *, admin_id, action, entity_type, entity_id,
  old_values, new_values, ip_address)` — inserts on the **caller's session**, so
  the entry commits atomically with the mutation it describes. A failing audit
  insert rolls back and logs instead of breaking the request (the mutation's own
  transaction semantics stay primary). A closed `ACTIONS` vocabulary documents
  the verbs; unknown actions/entities log a warning.

**Wired mutations (all admin-side):**

- `orders.py` — `PATCH /orders/{id}` records one entry per changed facet
  (`update_order_status`, `update_order_payment_status`,
  `update_order_tracking_code`) with real old→new values captured before the
  UPDATE; `POST /orders/{id}/cancel` (`cancel_order`);
  `PATCH /refunds/{id}` (`resolve_refund`, incl. the bank code and note).
- `products.py` — product create/update (name/price/stock/active tracked with
  old→new)/delete (soft-delete also audited); variant create/update (tracked
  fields old→new)/delete.
- `coupons.py` — coupon create/update (changed fields old→new).
- `reviews.py` — moderation (`moderate_review`) and admin-driven deletion
  (`delete_review`; customer deletions are not audited — they are not
  privileged).

**Read API:**

- `GET /admin/audit-logs` (`AdminUser` only): newest first, filters
  `action`, `entity_type`, `entity_id`, `admin_id`, `limit` ≤ 500; joins
  users/profiles for `admin_email`/`admin_name`.

## Files changed

- `backend/app/db.py` (AUDIT_DDL)
- `backend/app/services/audit.py` (new)
- `backend/app/routers/orders.py`, `products.py`, `coupons.py`, `reviews.py`,
  `admin.py`
- `backend/tests/api_smoke.py`
- Docs: `plan/backend-tasks.md`, `plan/README.md`, `plan/session-log.md`,
  `backend/README.md`, this audit.

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q      # 39 passed
./.venv/bin/python -m ruff check app tests          # clean
./.venv/bin/python tests/api_smoke.py               # 0 failed
# audit assertions (conditional sections need checkout stock):
#   audit log records the admin order mutation     entries=25
#   audit entries carry admin identity + timestamps
#   audit log filters by entity_id (refund resolution visible)
#   audit log is admin-only                        403
```

Manual: as admin, change an order's status or settle a refund, then
`GET /admin/audit-logs?entity_type=order&entity_id=<id>` — the old→new values
and the admin identity appear.

## What is NOT done / open

- **`ip_address` is always NULL** — needs the request object threaded through
  the routers (new checkbox in `backend-tasks.md`).
- **No UI** — the trail is API-only; an admin screen would belong to the F4.x
  shell work. Not requested.
- **Not tamper-resistant at the DB level** — REVOKE UPDATE/DELETE on the table
  for the app role is infra work (open checkbox added).
- **Role changes** are not auditable until B5.4 granular roles exist.
- `FEATURES.md`/`DESIGN_SYSTEM.md` untouched — no storefront capability or UI
  convention changed.
