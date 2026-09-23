# Audit — B2.5 Webhooks + background jobs (2026-09-23)

## Task

`B2.5` (P2, Batch F; depends on B2.1, which is done). Required:

- order events;
- a background job mechanism;
- abandoned-payment reminders;
- notification integration;
- idempotent job execution;
- retry behaviour.

B2.1 hand-off: add the `notification_deliveries` sweeper. Verification: worker
execution, a restart/retry test and a duplicate-event test. Part of the "continue the
whole backlog" run; the last P2 item.

## Spec check (Rule 0)

- **Epic A3 (webhooks/cron under `src/routes/api/public/*`, HMAC-verified):**
  - its location is the stale TanStack/Supabase stack, ignored;
  - the one inbound webhook this store has, the Zarinpal callback
    (`GET /payments/zarinpal/callback`), already exists and is idempotent
    (`already_paid` on a repeat);
  - Zarinpal does not sign callbacks; the payment is verified server-to-server.
- **D2 (transactional notifications only):** the reminder is added to that list
  (recorded under D2). It concerns the customer's own pending order, not marketing.
- **D5 (no stock reservation with TTL):** respected. Unpaid orders are reminded, never
  auto-cancelled.

## Recon / design (Rules 6–10)

- **Outbox.** `services/notifications.dispatch_deliveries()` was already retry-safe:
  it picks only `pending` / `failed` rows, with `FOR UPDATE SKIP LOCKED`, and
  increments `attempts`. What was missing was anything that would ever call it again.
  A row left `pending` by a crash stayed there forever.
- **Mechanism.** A small asyncio worker with no new dependency, rather than
  APScheduler (R12):
  - each job runs in **one transaction behind `pg_try_advisory_xact_lock('job:<name>')`**,
    so any number of workers is safe and a busy lock means "skip this tick";
  - the jobs are idempotent on their own as well: row locks and `event_key`
    uniqueness.
- **"Order events."** The lifecycle events themselves (created / paid / shipped /
  cancelled / refund) are already notified synchronously in their transactions
  (B2.1). The worker adds the time-based order event: an order still unpaid after the
  delay.
- **Outbound webhooks are NOT built.** Nothing names a consumer, a payload, a signing
  secret or a retry contract, and the rules say not to invent architecture. They are
  recorded as **B2.5a**, which needs a product decision.

## What was done

- **`app/services/jobs.py` (new):**
  - `run_job(name)`: advisory lock, the job, commit. It returns `None` when another
    worker holds the lock.
  - `run_all()`: a failing job is logged and does not stop the others.
  - **`sweep_deliveries`:** dispatches `pending` rows older than
    `NOTIFICATION_PENDING_STALE_SECONDS` (120). It retries `failed` rows once
    `updated_at` is older than `attempts × NOTIFICATION_RETRY_BACKOFF_SECONDS` (120)
    and `attempts < NOTIFICATION_RETRY_MAX_ATTEMPTS` (5). Batch of 100.
  - **`remind_unpaid_orders`:** targets orders that are `pending` + `unpaid`, older
    than `PAYMENT_REMINDER_AFTER_MINUTES` (60) and younger than
    `PAYMENT_REMINDER_MAX_AGE_HOURS` (72), so the first run after deploy does not
    remind ancient orders. It skips orders that already have their reminder, then
    calls `notify_order_event(…, "payment_reminder")`. In-app always; SMS/email only
    when switched on and configured (the B2.1 outbox).
- **`services/notifications.py`:** type `payment_reminder` («یادآوری پرداخت سفارش»)
  and its Persian message. Event key: `order:<id>:payment_reminder`.
- **`app/worker.py` (new):**
  - `python -m app.worker` runs a pass every `JOBS_INTERVAL_SECONDS` (60); `--once`
    runs one pass;
  - waits for in-flight outbox sends after each pass (`drain`);
  - stops on SIGTERM/SIGINT between passes;
  - runs no DDL.
- **`app/config.py`:** the six settings.
- **Infra:**
  - compose service `worker` (backend image, `command: python -m app.worker`,
    `depends_on: db-init completed`);
  - the backend's environment is anchored (`&backend_runtime_env`) and reused, so the
    worker has the same database and provider settings;
  - both `.env.example` files list the new variables.

## Files changed

- `backend/app/services/jobs.py` (new), `backend/app/worker.py` (new),
  `backend/app/services/notifications.py`, `backend/app/config.py`
- `backend/tests/test_jobs.py` (new, 12 tests)
- `infra/docker-compose.yml`, `infra/.env.example`, `backend/.env.example`
- docs:
  - `backend/README.md` ("Background jobs", tree, outbox note);
  - `infra/README.md` (services table);
  - `plan/RULES.md` (canonical table);
  - `plan/MASTER-BACKLOG.md` (D2 note, B2.5a);
  - `plan/backend-tasks.md` (+B2.5a);
  - `vogue-vintage-vibes/FEATURES.md` (۳.۸);
  - this audit;
  - `plan/session-log.md`, `plan/README.md`.

## How to verify

`pytest tests/test_jobs.py`: **12 passed**, with a faked provider.

- **Due order:** an order that is due gets exactly one reminder, with the right key,
  data, title and message.
- **Not due** (parametrised): too young; older than 72 h; paid; cancelled; processing.
- **Duplicate event:** run twice (a restarted worker's next pass), then three at once:
  still one reminder.
- **Lock held by another worker:** the job returns `None` and does nothing, then runs
  once the lock is free.
- **Sweeper:**
  - a 10-minute-old `pending` row (a lost send) → `sent` (attempts 1);
  - a fresh `pending` row is left to its after-commit sender;
  - a `sent` row is untouched.
- **Retry:**
  - a `failed` row with attempts 1 is retried and fails again (2);
  - attempts 4 inside its backoff: untouched;
  - attempts 5 (the cap): never retried;
  - after the backoff with the provider healthy: `sent` (3).
- **Isolation:** one failing job does not stop the others.
- **`worker.main(once=True)`** runs a pass and exits.

Mutation controls, each failing exactly its target:

| Mutation | Fails |
| --- | --- |
| (a) the lock ignored | "held by another worker" |
| (b) no cap | "up to the cap" (attempts 6) |
| (c) fresh `pending` rows swept | "what a crash left pending" |

Full gates (dev):

- `ruff` clean;
- `pytest -q` **267 passed**;
- smoke **245/0**.

**Clean environment (R14) + live worker:**

- `docker compose down -v && up -d --build`: `db-init` exits 0 with **4** stages,
  `/health` is ok, and **`worker` is running**, logging `started (every 60s)` and
  `pass done {'sweep_deliveries': 0, 'remind_unpaid_orders': 0}`.
- **Live flow:** a real checkout aged 2 h in SQL, then `docker compose exec worker
  python -m app.worker --once`.
  - `GET /notifications` shows **1** «یادآوری پرداخت سفارش» for that order;
  - a second pass: still 1;
  - `docker compose restart worker`: it runs again and logs a pass, and there is
    still **1**.
- `pytest -q` 267 and smoke 245/0 on the clean stack. The worker logs contain 0
  errors.

**Verification level:** clean-environment tested (unit, integration and live worker).

## What is NOT done / open

- **B2.5a (new, P3; needs a product decision):** outbound order webhooks. A decision
  must say who consumes them, the payload, the HMAC signing secret (env only) and the
  retry policy. The worker and outbox patterns here are what the implementation
  would reuse.
- **The worker has no hot reload.** `docker compose restart worker` after changing
  jobs (documented).
- **At-least-once across a crash mid-send.** A crash between a provider accepting a
  message and the row being marked `sent` can send twice on retry. This is the
  standard outbox trade-off, and it is documented.
- `DESIGN_SYSTEM.md`, frontend READMEs: untouched (no UI change; the reminder renders
  through the existing bell and `/account/notifications`).
