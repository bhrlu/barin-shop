"""Background jobs (B2.5), run by the worker (`python -m app.worker`).

Each job runs in one transaction that first takes a Postgres advisory lock named
after the job, so any number of workers (or a manual `--once` run next to the
service) execute a job at most once at a time; the loser just skips that tick. The
jobs are idempotent on their own too, so a crash mid-run is repaired by the next run:

* `sweep_deliveries` — the B2.1 outbox: re-dispatches deliveries left `pending` by a
  lost after-commit send (a crash or restart) and retries `failed` ones after
  `attempts × backoff`, up to a cap. `dispatch_deliveries` locks each row with
  `SKIP LOCKED` and skips `sent` / `skipped` rows, so a row is never sent twice by
  two dispatchers (delivery is at-least-once only across a crash *during* a send);
* `remind_unpaid_orders` — one in-app «یادآوری پرداخت» (plus SMS / email when those
  channels are on) for each order still `pending` and `unpaid` after
  `payment_reminder_after_minutes`, through the canonical `notify_order_event`;
  `UNIQUE(user_id, event_key)` makes a second reminder for the same order a no-op.
"""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.services.notifications import dispatch_deliveries, notify_order_event

log = logging.getLogger(__name__)

BATCH = 100

Job = Callable[[AsyncSession], Awaitable[int]]


async def sweep_deliveries(session: AsyncSession) -> int:
    ids = [
        str(row[0])
        for row in (
            await session.execute(
                text(
                    "SELECT id FROM public.notification_deliveries "
                    "WHERE (status = 'pending' "
                    "       AND created_at < now() - make_interval(secs => :stale)) "
                    "   OR (status = 'failed' AND attempts < :max_attempts "
                    "       AND updated_at < now() - make_interval(secs => :backoff * attempts)) "
                    "ORDER BY created_at LIMIT :batch"
                ),
                {
                    "stale": settings.notification_pending_stale_seconds,
                    "max_attempts": settings.notification_retry_max_attempts,
                    "backoff": settings.notification_retry_backoff_seconds,
                    "batch": BATCH,
                },
            )
        ).all()
    ]
    if ids:
        await dispatch_deliveries(ids)
    return len(ids)


async def remind_unpaid_orders(session: AsyncSession) -> int:
    due = (
        await session.execute(
            text(
                "SELECT o.id FROM public.orders o "
                "WHERE o.status = 'pending' AND o.payment_status = 'unpaid' "
                "  AND o.created_at < now() - make_interval(mins => :after) "
                "  AND o.created_at > now() - make_interval(hours => :max_age) "
                "  AND NOT EXISTS (SELECT 1 FROM public.notifications n "
                "                  WHERE n.user_id = o.user_id "
                "                    AND n.event_key = 'order:' || o.id || :suffix) "
                "ORDER BY o.created_at LIMIT :batch"
            ),
            {
                "suffix": ":payment_reminder",  # the key notify_order_event writes
                "after": settings.payment_reminder_after_minutes,
                "max_age": settings.payment_reminder_max_age_hours,
                "batch": BATCH,
            },
        )
    ).all()
    for (order_id,) in due:
        await notify_order_event(session, order_id, "payment_reminder")
    return len(due)


JOBS: dict[str, Job] = {
    "sweep_deliveries": sweep_deliveries,
    "remind_unpaid_orders": remind_unpaid_orders,
}


async def run_job(name: str) -> int | None:
    """Run one job under its advisory lock; `None` when another worker holds it."""
    async with SessionLocal() as session:
        locked = (
            await session.execute(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"job:{name}"},
            )
        ).scalar()
        if not locked:
            await session.rollback()
            return None
        count = await JOBS[name](session)
        await session.commit()  # releases the lock; queued outbox rows dispatch now
        return count


async def run_all() -> dict[str, int | None]:
    """One pass over every job. A failing job is logged and does not stop the others."""
    results: dict[str, int | None] = {}
    for name in JOBS:
        try:
            results[name] = await run_job(name)
        except Exception:  # noqa: BLE001 — one broken job must not stop the worker
            log.exception("job %s failed", name)
            results[name] = None
    return results
