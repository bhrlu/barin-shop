"""Outbound order webhooks (B2.5a, decision D11).

One generic integration: the five order-lifecycle events (`order.created`,
`order.paid`, `order.shipped`, `order.delivered`, `order.cancelled`) are
delivered as signed POSTs to the single endpoint configured by env
(`WEBHOOK_ORDER_URL` + `WEBHOOK_HMAC_SECRET` — the secret never lives in the
database, per D11). The payload is the **raw row dump** the owner chose: the
full `orders` row plus the order's `order_items` rows, wrapped in a minimal
envelope — internal columns are deliberately exposed to this consumer.

Delivery mirrors the notification outbox (`services/notifications.py`):

* `enqueue_order_event` writes one `webhook_deliveries` row on the caller's
  transaction (`UNIQUE (event, order_id)` makes a replayed event a no-op) and,
  when configured, queues its id for the shared after-commit dispatch so a
  healthy consumer usually gets the POST within the same second;
* the worker's `sweep_webhooks` job picks up whatever the after-commit send
  lost (crash/restart) and retries `failed` rows with exponential backoff
  (attempts × `WEBHOOK_RETRY_BACKOFF_SECONDS`, `WEBHOOK_RETRY_MAX_ATTEMPTS` = 5,
  then `failed` for good — an admin can re-queue from the deliveries screen);
* every attempt signs the raw body with HMAC-SHA256 and sends
  `X-SANDE-Signature: sha256=<hex>` so the consumer can verify it received
  exactly the bytes signed; `X-SANDE-Event` names the event and
  `X-SANDE-Delivery` the delivery id.

Anything answered `2xx` is `sent`; transport errors and non-2xx answers are
`failed` with the reason stored on the row (`response_status` keeps the HTTP
status the consumer returned). A redelivered row answering 2xx is still a
success — consumers deduplicate on the delivery id / (event, order_id).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import weakref
from collections.abc import Mapping
from datetime import date, datetime
from uuid import UUID

import httpx
from sqlalchemy import event as sa_event
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal

log = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-SANDE-Signature"
EVENT_HEADER = "X-SANDE-Event"
DELIVERY_HEADER = "X-SANDE-Delivery"

# D11: the five lifecycle events, in one place (Rule 10: a closed set). The
# caller-facing names (`created`, `paid`, …) match the notification event names
# so both can be fired from the same lifecycle line; the wire names are what
# the consumer sees.
EVENTS: dict[str, str] = {
    "created": "order.created",
    "paid": "order.paid",
    "shipped": "order.shipped",
    "delivered": "order.delivered",
    "cancelled": "order.cancelled",
}


def configured() -> bool:
    """Webhooks are off until both the endpoint URL and the secret exist."""
    return bool(settings.webhook_order_url) and bool(settings.webhook_hmac_secret)


def state() -> dict:
    """Read-only state for `/admin/settings/webhooks` (no secret is returned)."""
    return {
        "enabled": configured(),
        "url": settings.webhook_order_url or None,
        "events": sorted(EVENTS.values()),
        "retry_max_attempts": settings.webhook_retry_max_attempts,
        "retry_backoff_seconds": settings.webhook_retry_backoff_seconds,
    }


def sign(secret: str, body: bytes) -> str:
    """`sha256=<hex>` HMAC-SHA256 over exactly the bytes on the wire."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _jsonable(value):
    """One JSON-safe conversion for the raw dump: dates/UUIDs become strings,
    JSONB comes back ready, everything else passes through."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def webhook_payload(event: str, occurred_at, order_row: Mapping, item_rows: list[Mapping]) -> dict:
    """The D11 envelope: `{event, occurred_at, order, items}` — raw row dump."""
    return {
        "event": event,
        "occurred_at": _jsonable(occurred_at),
        "order": {k: _jsonable(v) for k, v in order_row.items()},
        "items": [{k: _jsonable(v) for k, v in row.items()} for row in item_rows],
    }


# --- enqueue (caller's transaction) -----------------------------------------------------


async def enqueue_order_event(session: AsyncSession, order_id: UUID | str, event_name: str) -> None:
    """Write the outbox row for one lifecycle event (no commit, no network here).

    Call it next to `notify_order_event` at the business points. Webhooks off →
    nothing is written (an unconfigured store leaves no trail). Unknown event
    name → a warning and no row (the closed set in `EVENTS` is the contract;
    `created_preorder` maps onto the canonical `order.created`).
    """
    event = EVENTS.get(event_name)
    if event is None:
        log.warning("webhook: unknown lifecycle event %r — no delivery", event_name)
        return
    if not configured():
        return
    row_id = (
        await session.execute(
            text(
                "INSERT INTO public.webhook_deliveries (event, order_id) "
                "VALUES (:event, CAST(:oid AS uuid)) "
                "ON CONFLICT (event, order_id) DO NOTHING RETURNING id"
            ),
            {"event": event, "oid": str(order_id)},
        )
    ).scalar()
    if row_id is not None:
        session.info.setdefault(_QUEUE_KEY, []).append(str(row_id))


# --- after-commit dispatch (shared pattern with notifications) --------------------------

_QUEUE_KEY = "webhook_deliveries"
_inflight: set[asyncio.Task] = set()
# at most two outbound POSTs hold a pooled connection at once (pool is 5 + 5)
_slots: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


@sa_event.listens_for(Session, "after_commit")
def _dispatch_webhooks_after_commit(sync_session: Session) -> None:
    if sync_session.in_nested_transaction():
        return  # a SAVEPOINT release: nothing is durable until the outer COMMIT
    ids = sync_session.info.pop(_QUEUE_KEY, None)
    if not ids:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # sync context: outbox rows stay `pending` for the sweeper
        log.warning("webhook: no running loop; %d delivery(ies) left pending", len(ids))
        return
    task = loop.create_task(dispatch_webhooks(ids))
    _inflight.add(task)
    task.add_done_callback(_inflight.discard)


@sa_event.listens_for(Session, "after_transaction_end")
def _drop_webhooks_after_rollback(sync_session: Session, transaction) -> None:
    # after_commit has already taken the queue on success; anything left when
    # the outer transaction ends was rolled back with the outbox row
    if transaction.parent is None:
        sync_session.info.pop(_QUEUE_KEY, None)


async def dispatch_webhooks(delivery_ids: list[str]) -> None:
    """Deliver the given outbox rows. Safe to re-run: `sent`/`skipped` rows are
    left alone and in-progress rows are `SKIP LOCKED`, so two dispatchers never
    double-send (at-least-once only across a crash *during* a POST)."""
    loop = asyncio.get_running_loop()
    slots = _slots.setdefault(loop, asyncio.Semaphore(2))
    for delivery_id in delivery_ids:
        async with slots:
            try:
                await _deliver_one(delivery_id)
            except Exception:  # noqa: BLE001 — a background send must never crash the app
                log.exception("webhook: delivery %s crashed", delivery_id)


async def _deliver_one(delivery_id: str) -> None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, event, order_id, created_at FROM public.webhook_deliveries "
                    "WHERE id = CAST(:did AS uuid) AND status IN ('pending', 'failed') "
                    "FOR UPDATE SKIP LOCKED"
                ),
                {"did": delivery_id},
            )
        ).mappings().first()
        if row is None:
            return  # already sent/skipped, or another sender holds the row

        order = (
            await session.execute(
                text("SELECT * FROM public.orders WHERE id = CAST(:oid AS uuid)"),
                {"oid": str(row["order_id"])},
            )
        ).mappings().first()
        if order is None:
            # the order row is gone (hard-deleted probe/teardown) — nothing to deliver
            await _finish(session, delivery_id, "skipped", "order_gone", None, 0)
            return
        items = (
            await session.execute(
                text(
                    "SELECT * FROM public.order_items WHERE order_id = CAST(:oid AS uuid) "
                    "ORDER BY id"
                ),
                {"oid": str(row["order_id"])},
            )
        ).mappings().all()
        payload = webhook_payload(
            row["event"], row["created_at"], dict(order), [dict(item) for item in items]
        )
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()

        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(
                    settings.webhook_order_url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        SIGNATURE_HEADER: sign(settings.webhook_hmac_secret, body),
                        EVENT_HEADER: row["event"],
                        DELIVERY_HEADER: str(row["id"]),
                    },
                )
            if 200 <= response.status_code < 300:
                await _finish(session, delivery_id, "sent", None, response.status_code, 1)
            else:
                await _finish(
                    session,
                    delivery_id,
                    "failed",
                    f"HTTP {response.status_code}",
                    response.status_code,
                    1,
                )
        except httpx.HTTPError as exc:
            await _finish(session, delivery_id, "failed", str(exc), None, 1)
        except Exception as exc:  # noqa: BLE001
            await _finish(session, delivery_id, "failed", type(exc).__name__, None, 1)


async def _finish(
    session: AsyncSession,
    delivery_id: str,
    status: str,
    error: str | None,
    response_status: int | None,
    attempted: int,
) -> None:
    await session.execute(
        text(
            "UPDATE public.webhook_deliveries SET status = :status, last_error = :error, "
            "response_status = :rstatus, attempts = attempts + :tried, updated_at = now() "
            "WHERE id = CAST(:did AS uuid)"
        ),
        {
            "status": status,
            "error": error,
            "rstatus": response_status,
            "tried": attempted,
            "did": delivery_id,
        },
    )
    await session.commit()


# --- admin redeliver + worker sweep -----------------------------------------------------


async def redeliver(session: AsyncSession, delivery_id: UUID | str) -> dict:
    """Re-queue a failed delivery (admin action, audited by the caller).

    Sent immediately after the caller's commit. A `sent` delivery is refused —
    the consumer already has it, and re-POSTing would be a duplicate they never
    asked for. Returns the re-queued row or `{}` when nothing was eligible.
    """
    row = (
        await session.execute(
            text(
                "UPDATE public.webhook_deliveries SET status = 'pending', last_error = NULL, "
                "updated_at = now() WHERE id = CAST(:did AS uuid) AND status = 'failed' "
                "RETURNING id, event, order_id"
            ),
            {"did": str(delivery_id)},
        )
    ).mappings().first()
    if row is None:
        return {}
    session.info.setdefault(_QUEUE_KEY, []).append(str(row["id"]))
    return {"id": str(row["id"]), "event": row["event"], "order_id": str(row["order_id"])}


async def sweep_webhooks(session: AsyncSession) -> int:
    """Worker job: dispatch lost `pending` rows and retry `failed` ones after
    attempts × backoff, up to the cap (mirrors `sweep_deliveries`)."""
    ids = [
        str(row[0])
        for row in (
            await session.execute(
                text(
                    "SELECT id FROM public.webhook_deliveries "
                    "WHERE (status = 'pending' "
                    "       AND created_at < now() - make_interval(secs => :stale)) "
                    "   OR (status = 'failed' AND attempts < :max_attempts "
                    "       AND updated_at < now() - make_interval(secs => :backoff * attempts)) "
                    "ORDER BY created_at LIMIT 100"
                ),
                {
                    "stale": settings.webhook_pending_stale_seconds,
                    "max_attempts": settings.webhook_retry_max_attempts,
                    "backoff": settings.webhook_retry_backoff_seconds,
                },
            )
        ).all()
    ]
    if ids:
        await dispatch_webhooks(ids)
    return len(ids)


async def drain() -> None:
    """Wait for in-flight background dispatches (tests, graceful shutdown)."""
    while _inflight:
        await asyncio.gather(*list(_inflight), return_exceptions=True)
