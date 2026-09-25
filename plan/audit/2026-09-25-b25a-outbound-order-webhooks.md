# 2026-09-25 — B2.5a Outbound order webhooks (decision D11)

## Task

`plan/MASTER-BACKLOG.md` §B2.5a (Batch F, P3, backend; depends on B2.5 DONE):
send order-lifecycle events to external systems. The task was gated on a
product decision (§18 stop condition); the user made that decision this
session, recorded as **decision D11**:

* **Events:** the five order-lifecycle events only — `order.created`,
  `order.paid`, `order.shipped`, `order.delivered`, `order.cancelled`.
* **Payload:** raw row dump — the full `orders` row + its `order_items` rows,
  wrapped as `{event, occurred_at, order, items}` (internal columns
  deliberately exposed; the consumer was chosen by the owner with that in
  mind).
* **Endpoint + secret:** env-only (`WEBHOOK_ORDER_URL`, `WEBHOOK_HMAC_SECRET`).
* **Delivery:** outbox table, after-commit send, exponential backoff ×5
  (1 → 60 s base), admin redeliver; guard `StaffSettings`, mutations audited.

## Spec check (Rule 0)

Sections located via the CONTEXT-MAP index: [BE-04] admin audit logging (the
redeliver endpoint is audited through the canonical `record_audit`), [BE-05]
atomic transaction safeguards (enqueue runs on the caller's transaction —
a rolled-back order leaves no outbox row), B1.4 invariants (Rule 10/11
respect: no new status strings, money untouched). The spec has no outbound
webhook section (B4.13's grep precedent); D11 is the authority. No spec file
edited.

## What was done

1. **`webhook_deliveries` outbox** (`WEBHOOK_DDL` in `app/db.py`, idempotent,
   registered in `startup_ddl()`): `event` CHECK-constrained to the D11 set,
   `order_id` FK cascade, `status ∈ pending/sent/failed/skipped`, `attempts`,
   `last_error`, `response_status`, **`UNIQUE (event, order_id)`** (a replayed
   lifecycle event is a no-op), partial index on open rows. DML-only app role
   gets CRUD via the existing `ALTER DEFAULT PRIVILEGES` grant (no grant
   change needed — proven live).
2. **`app/services/webhooks.py`** — the one implementation (R7), mirroring the
   notification outbox: `enqueue_order_event(session, order_id, event_name)`
   writes the row on the caller's transaction and queues the id in
   `session.info`; `after_commit` listener dispatches (a rollback drops the
   queue); `dispatch_webhooks` → `_deliver_one` locks the row
   `FOR UPDATE SKIP LOCKED`, dumps `SELECT *` from `orders` + `order_items`
   (`ORDER BY id` — **`order_items` has no `created_at`**; caught by the live
   probe, not by unit tests), signs the raw body
   (`X-SANDE-Signature: sha256=<hex>` HMAC-SHA256, plus `X-SANDE-Event`,
   `X-SANDE-Delivery`), POSTs with `httpx` (already a dependency); 2xx = sent,
   anything else failed with the HTTP status stored. `redeliver` re-queues
   only `failed` rows; `sweep_webhooks` re-dispatches stale `pending` and
   retries `failed` after `attempts × WEBHOOK_RETRY_BACKOFF_SECONDS` (60) up
   to `WEBHOOK_RETRY_MAX_ATTEMPTS` (5). ASCII header names (`X-SANDE-*`) —
   non-ASCII header names are invalid per RFC 7230.
3. **Lifecycle hooks** (one line each, next to the existing
   `notify_order_event` calls): `services/checkout.py` (order.created, for
   both normal and preorder checkouts), `services/order_lifecycle.py`
   `cancel_order_tx` (order.cancelled), `routers/orders.py` staff PATCH
   (shipped / delivered / paid) and payment-complete (paid).
4. **Worker**: `sweep_webhooks` registered in `JOBS` (`services/jobs.py`) —
   advisory-locked like the other jobs, no new service.
5. **Admin surface** (`app/routers/webhooks.py`, guard `StaffSettings` =
   `settings` capability, same as the notification switches):
   `GET /admin/settings/webhooks` (read-only state; **never returns the
   secret**), `GET /admin/webhooks/deliveries` (Page envelope, status filter),
   `POST /admin/webhooks/deliveries/{id}/redeliver` (409 for non-`failed`,
   audited as `redeliver_webhook`). Registered in `app/main.py`.
6. **Config/env**: `webhook_*` settings in `app/config.py`; documented
   `WEBHOOK_*` block in `infra/.env.example`; `backend/README.md` gains the
   "Outbound order webhooks (B2.5a, decision D11)" section (endpoint, headers,
   payload, retry, admin surface, env-only secret) and the new job in the
   worker list.

## Tests

* `tests/test_webhook_units.py` (new, 6): the closed event set; signature
  equals a reference HMAC; `configured()` requires both values; state never
  leaks the secret; payload envelope shape (raw dump keeps columns and nulls);
  UUID/datetime → ISO-string JSON safety.
* `tests/test_webhook_outbox.py` (new, 7, DB-backed, skip-without-Postgres,
  throwaway rows removed in teardown): unconfigured store writes no row;
  `cancel_order_tx` enqueues exactly one pending row; replay is a no-op;
  unknown event refused; `redeliver` refuses non-failed, re-queues failed;
  sweeper eligibility respects the stale window and the attempts × backoff
  window; outbox row cascades away with its order.
* `tests/api_smoke.py` (+4 checks): webhook state shape for admin, 403 for
  customer and support on both new GET surfaces, deliveries envelope.

## Verification

* `ruff check app tests` — clean (one `--fix` import-sort pass on `main.py`).
* `pytest -q` — **409 passed** (was 396; +13; 0 skipped DB modules).
* OpenAPI — **77 paths** (was 74; the three new webhook paths registered).
* **Clean environment (Rule 14)**: `docker compose down -v && up -d --build`;
  `db-init` exited 0 with all four seed stages; postgres/minio/backend healthy;
  `/health` ok; live OpenAPI shows the 3 new paths; the running API role
  (`sande_app`) has INSERT/SELECT/UPDATE on `webhook_deliveries` via the
  default privileges — no grant change required.
* Smoke against the clean stack — **275 routes/checks, 0 failed**.
* **Live end-to-end probe** (throwaway receiver mounted in the *real* API
  process via the dev bind-mount + `--reload`; `webhook_order_url` pointed at
  it): `cancel_order_tx` → outbox row `sent / attempts 1 / response 200` and
  the receiver recorded `sig_ok: true`, `event: order.cancelled`, envelope
  keys `{event, items, occurred_at, order}`, 15-column raw order dump, items
  present, `occurred_at` set. The first probe run caught a real bug (guessed
  `order_items.created_at` — the column does not exist), fixed to
  `ORDER BY id` and re-proven. Probe rows hard-deleted afterwards (0 rows, 0
  orders, 0 users, 0 products remain); the throwaway receiver was removed and
  the bind-mounted `main.py` restored (verified via grep + `git status`).

## Deliberate interpretation (recorded, per R15)

* **Raw dump includes internal columns** (user_id, payment ids, shipping
  address) — that is D11's explicit choice; consumers are owner-selected. A
  payload change is a breaking version per D11.
* **`created_preorder` checkout still delivers `order.created`** — the wire
  set is exactly the five D11 events; the preorder distinction is a
  notification-copy concern, not a webhook event.
* **Delivery is at-least-once** (crash during a POST can double-send);
  consumers deduplicate via `X-SANDE-Delivery` / `(event, order_id)` — stated
  in the service docstring and README.
* **`occurred_at` is the delivery row's `created_at`** (the moment the event
  was recorded), not the order's `updated_at` (which moves on unrelated
  edits).

## What is NOT done / open

* No real external consumer exists yet — the receiving side was proven with a
  throwaway in-process receiver; wiring an actual ERP/courier consumer is a
  future integration task when one exists.
* No admin UI screen for deliveries (the API surface is complete; a screen can
  follow the `AdminDataTable` pattern if wanted — not part of B2.5a).
* No retry jitter (backoff is deterministic attempts × 60 s) — acceptable for
  a single consumer; revisit if several consumers are added.

## Docs synced

`plan/MASTER-BACKLOG.md` (decision D11 §4 + §11 + §16 + JSON B2.5a DONE + counts
56/4 of 61), `plan/backend-tasks.md` (B2.5a checkbox + Done paragraph),
`backend/README.md` (webhook section + worker job), `infra/.env.example`,
`plan/session-log.md`, this audit.
