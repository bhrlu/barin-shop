"""Canonical notification service (B2.1, decision D2).

Business code calls `notify_order_event` / `notify_refund_event` (or `notify`)
on its own session, at the lifecycle point where the event really happens:

    business event ──► notify() ──► notifications row        (in-app inbox)
                                └─► notification_deliveries  (SMS / email outbox)
                                          │
                               after COMMIT ▼
                                  dispatch_deliveries() ──► provider.send()

* The inbox row is inserted on the caller's session, so it commits or rolls
  back with the business change. There is no second transaction to go wrong.
* UNIQUE (user_id, event_key) is the only dedup mechanism: a repeated
  transition (`order:<id>:paid`, …) inserts nothing, and since outbox rows are
  created only next to a *new* inbox row, nothing is sent twice either.
* The in-app inbox is always on. SMS/email get an outbox row only when the
  admin switched the channel on (`notification_settings`). A row is `pending`
  only if the provider is configured (environment credentials) and a recipient
  exists; otherwise it is recorded as `skipped` with the reason.
* Pending rows are sent in the background *after* the commit (SQLAlchemy
  `after_commit`), so a slow or failing provider can never block, fail or roll
  back an order, payment or refund. Failures are stored on the row
  (`failed` + `last_error`). `dispatch_deliveries` only picks `pending`/`failed`
  rows under a row lock, so re-running it (a retry) never re-sends a `sent` one.

There is deliberately no job queue here (that is B2.5): if the process dies
between the commit and the send, the row stays `pending` for a future sweeper.
"""

import asyncio
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from weakref import WeakKeyDictionary

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services import notification_providers as providers
from app.services.notification_providers import ProviderError

log = logging.getLogger(__name__)

CHANNELS = ("sms", "email")
BRAND = "ساندِه"


@dataclass(frozen=True)
class NotificationType:
    """An event the store tells customers about, and where it goes besides the inbox."""

    title: str
    channels: tuple[str, ...]


# Transactional scope of decision D2 that has a live flow today. The password
# reset (F2.3) is email-only and goes through `queue_private_email` below;
# preorder (B4.13) has no flow yet and adds its type with it.
TYPES: dict[str, NotificationType] = {
    "order_created": NotificationType("سفارش شما ثبت شد", CHANNELS),
    "order_paid": NotificationType("پرداخت سفارش تأیید شد", CHANNELS),
    "order_shipped": NotificationType("سفارش شما ارسال شد", CHANNELS),
    "order_cancelled": NotificationType("سفارش لغو شد", CHANNELS),
    "refund_approved": NotificationType("درخواست بازپرداخت تأیید شد", CHANNELS),
    "refund_settled": NotificationType("مبلغ بازپرداخت واریز شد", CHANNELS),
}

_ORDER_EVENTS = {
    "created": "order_created",
    "paid": "order_paid",
    "shipped": "order_shipped",
    "cancelled": "order_cancelled",
}
_REFUND_EVENTS = {"approved": "refund_approved", "settled": "refund_settled"}

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ASCII_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa(value: object) -> str:
    """Persian digits (spec B1.4) for numbers shown to the customer."""
    return str(value).translate(_FA_DIGITS)


def toman(amount: int) -> str:
    """`۳۵۰,۰۰۰` — the storefront's `formatToman` format (spec B4.1)."""
    return fa(f"{int(amount):,}")


def normalize_phone(phone: str | None) -> str | None:
    """ASCII digits only (customers type Persian digits); None when empty."""
    if not phone:
        return None
    digits = re.sub(r"[^\d+]", "", phone.translate(_ASCII_DIGITS))
    return digits or None


# --- messages ---------------------------------------------------------------------


def order_message(event_name: str, order: Mapping[str, Any]) -> str:
    number = fa(order["order_number"])
    if event_name == "created":
        return (
            f"سفارش شماره {number} به مبلغ {toman(order['total'])} تومان ثبت شد "
            "و در انتظار پرداخت است."
        )
    if event_name == "paid":
        return (
            f"پرداخت سفارش شماره {number} به مبلغ {toman(order['total'])} تومان تأیید شد "
            "و سفارش در حال آماده‌سازی است."
        )
    if event_name == "shipped":
        text_ = f"سفارش شماره {number} ارسال شد."
        if order.get("tracking_code"):
            # identifiers stay in Latin digits so they can be copied into the carrier's site
            text_ += f" کد رهگیری مرسوله: {order['tracking_code']}"
        return text_
    if event_name == "cancelled":
        text_ = f"سفارش شماره {number} لغو شد."
        if order.get("payment_status") == "paid":
            text_ += " برای بازگشت وجه می‌توانید از صفحه سفارش درخواست بازپرداخت ثبت کنید."
        return text_
    raise ValueError(f"unknown order event {event_name!r}")


def refund_message(event_name: str, refund: Mapping[str, Any]) -> str:
    number = fa(refund["order_number"])
    amount = toman(refund["amount"])
    if event_name == "approved":
        return (
            f"درخواست بازپرداخت سفارش شماره {number} به مبلغ {amount} تومان تأیید شد "
            "و به‌زودی واریز می‌شود."
        )
    if event_name == "settled":
        text_ = f"مبلغ {amount} تومان بابت سفارش شماره {number} به حساب شما واریز شد."
        if refund.get("bank_tracking_code"):
            text_ += f" کد رهگیری بانکی: {refund['bank_tracking_code']}"
        return text_
    raise ValueError(f"unknown refund event {event_name!r}")


# --- admin switches -----------------------------------------------------------------


async def load_switches(session: AsyncSession) -> dict[str, Any]:
    """The single `notification_settings` row (defaults when it is missing)."""
    row = (
        await session.execute(
            text(
                "SELECT sms_enabled, email_enabled, updated_at, updated_by "
                "FROM public.notification_settings WHERE id"
            )
        )
    ).mappings().first()
    if row is None:
        return {"sms": False, "email": False, "updated_at": None, "updated_by": None}
    return {
        "sms": bool(row["sms_enabled"]),
        "email": bool(row["email_enabled"]),
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }


async def save_switches(
    session: AsyncSession, *, sms: bool | None, email: bool | None, admin_id: UUID
) -> None:
    """Update the admin switches (caller audits + commits)."""
    await session.execute(
        text(
            "INSERT INTO public.notification_settings "
            "(id, sms_enabled, email_enabled, updated_by, updated_at) "
            "VALUES (true, COALESCE(:sms, false), COALESCE(:email, false), "
            "        CAST(:admin AS uuid), now()) "
            "ON CONFLICT (id) DO UPDATE SET "
            "  sms_enabled = COALESCE(:sms, notification_settings.sms_enabled), "
            "  email_enabled = COALESCE(:email, notification_settings.email_enabled), "
            "  updated_by = CAST(:admin AS uuid), updated_at = now()"
        ),
        {"sms": sms, "email": email, "admin": str(admin_id)},
    )


def channel_state(switches: Mapping[str, Any]) -> dict[str, Any]:
    """What each external channel will actually do: switch AND provider config."""
    sms = providers.sms_provider()
    email = providers.email_provider()
    return {
        "internal_enabled": True,  # the in-app inbox cannot be switched off
        "sms_enabled": switches["sms"],
        "sms_provider": sms.name,
        "sms_configured": sms.configured(),
        "sms_active": switches["sms"] and sms.configured(),
        "email_enabled": switches["email"],
        "email_provider": email.name,
        "email_configured": email.configured(),
        "email_active": switches["email"] and email.configured(),
        "updated_at": switches["updated_at"].isoformat() if switches["updated_at"] else None,
        "updated_by": str(switches["updated_by"]) if switches["updated_by"] else None,
    }


# --- creating notifications -----------------------------------------------------------


async def notify(
    session: AsyncSession,
    *,
    user_id: UUID | str,
    type_: str,
    event_key: str,
    message: str,
    data: Mapping[str, Any] | None = None,
    fallback_phone: str | None = None,
) -> str | None:
    """Record one business event for one user; returns the new id, or None on a repeat.

    Runs on the caller's session and never commits. A database error propagates
    on purpose: the event and its notification commit together or not at all.
    """
    spec = TYPES[type_]
    row = (
        await session.execute(
            text(
                "INSERT INTO public.notifications "
                "(user_id, type, title, message, data, event_key) "
                "VALUES (CAST(:uid AS uuid), :type, :title, :message, "
                "        CAST(:data AS jsonb), :key) "
                "ON CONFLICT (user_id, event_key) DO NOTHING RETURNING id"
            ),
            {
                "uid": str(user_id),
                "type": type_,
                "title": spec.title,
                "message": message,
                "data": json.dumps(dict(data or {}), ensure_ascii=False, default=str),
                "key": event_key,
            },
        )
    ).first()
    if row is None:
        return None  # this event was already recorded (and, if due, sent)
    notification_id = str(row[0])

    switches = await load_switches(session)
    wanted = [channel for channel in spec.channels if switches[channel]]
    if wanted:
        await _enqueue_deliveries(session, notification_id, user_id, wanted, fallback_phone)
    return notification_id


async def _enqueue_deliveries(
    session: AsyncSession,
    notification_id: str,
    user_id: UUID | str,
    channels: list[str],
    fallback_phone: str | None,
) -> None:
    contact = (
        await session.execute(
            text(
                "SELECT u.email, p.phone FROM public.users u "
                "LEFT JOIN public.profiles p ON p.id = u.id WHERE u.id = CAST(:uid AS uuid)"
            ),
            {"uid": str(user_id)},
        )
    ).mappings().first() or {}
    recipients = {
        # the account's phone first; the order's shipping phone when it has none
        "sms": normalize_phone(contact.get("phone")) or normalize_phone(fallback_phone),
        "email": (contact.get("email") or "").strip() or None,
    }
    queued: list[str] = []
    for channel in channels:
        provider = providers.sms_provider() if channel == "sms" else providers.email_provider()
        recipient = recipients[channel]
        if not provider.configured():
            status, reason = "skipped", "provider_not_configured"
        elif not recipient:
            status, reason = "skipped", "no_recipient"
        else:
            status, reason = "pending", None
        delivery_id = (
            await session.execute(
                text(
                    "INSERT INTO public.notification_deliveries "
                    "(notification_id, channel, recipient, status, provider, last_error) "
                    "VALUES (CAST(:nid AS uuid), :channel, :recipient, :status, :provider, "
                    "        :reason) "
                    "ON CONFLICT (notification_id, channel) DO NOTHING RETURNING id"
                ),
                {
                    "nid": notification_id,
                    "channel": channel,
                    "recipient": recipient,
                    "status": status,
                    "provider": provider.name,
                    "reason": reason,
                },
            )
        ).scalar()
        if delivery_id is not None and status == "pending":
            queued.append(str(delivery_id))
    if queued:
        session.info.setdefault(_QUEUE_KEY, []).extend(queued)


async def notify_order_event(session: AsyncSession, order_id: UUID | str, event_name: str) -> None:
    """`created` / `paid` / `shipped` / `cancelled` for the order's owner.

    Call it right after the status change, on the same session. Reads the order
    as that transaction sees it (e.g. the tracking code set in the same PATCH).
    """
    type_ = _ORDER_EVENTS[event_name]
    order = (
        await session.execute(
            text(
                "SELECT id, user_id, order_number, total, payment_status, tracking_code, "
                "shipping_address->>'phone' AS shipping_phone "
                "FROM public.orders WHERE id = CAST(:oid AS uuid)"
            ),
            {"oid": str(order_id)},
        )
    ).mappings().first()
    if order is None:
        log.warning("notify: order %s not found for %s", order_id, event_name)
        return
    await notify(
        session,
        user_id=order["user_id"],
        type_=type_,
        event_key=f"order:{order['id']}:{event_name}",
        message=order_message(event_name, order),
        data={"order_id": str(order["id"]), "order_number": order["order_number"]},
        fallback_phone=order["shipping_phone"],
    )


async def notify_refund_event(
    session: AsyncSession, refund_id: UUID | str, event_name: str
) -> None:
    """`approved` / `settled` for the refund's claimant, on the resolving session."""
    type_ = _REFUND_EVENTS[event_name]
    refund = (
        await session.execute(
            text(
                "SELECT r.id, r.user_id, r.amount, r.bank_tracking_code, r.order_id, "
                "o.order_number, o.shipping_address->>'phone' AS shipping_phone "
                "FROM public.refund_requests r JOIN public.orders o ON o.id = r.order_id "
                "WHERE r.id = CAST(:rid AS uuid)"
            ),
            {"rid": str(refund_id)},
        )
    ).mappings().first()
    if refund is None:
        log.warning("notify: refund %s not found for %s", refund_id, event_name)
        return
    await notify(
        session,
        user_id=refund["user_id"],
        type_=type_,
        event_key=f"refund:{refund['id']}:{event_name}",
        message=refund_message(event_name, refund),
        data={
            "order_id": str(refund["order_id"]),
            "order_number": refund["order_number"],
            "refund_id": str(refund["id"]),
        },
        fallback_phone=refund["shipping_phone"],
    )


# --- email-only messages that must not be stored --------------------------------------


async def queue_private_email(
    session: AsyncSession, *, to: str, subject: str, body: str, kind: str
) -> str:
    """Send one email whose body carries a secret (e.g. a password-reset link).

    Same channel rule as every notification — only when the admin switched email
    on AND SMTP is configured — and, like the outbox, only after the caller's
    COMMIT (a rolled-back request sends nothing). Unlike the outbox nothing is
    written to `notification_deliveries`: that row would put the secret in the
    database. It is sent once; a failure is logged (never the body) and the user
    can simply ask again. Returns "queued", "email_disabled" or
    "provider_not_configured".
    """
    switches = await load_switches(session)
    if not switches["email"]:
        log.info("notify: %s email not sent — email channel switched off", kind)
        return "email_disabled"
    if not providers.email_provider().configured():
        log.info("notify: %s email not sent — SMTP not configured", kind)
        return "provider_not_configured"
    session.info.setdefault(_PRIVATE_KEY, []).append(
        {"to": to, "subject": subject, "body": body, "kind": kind}
    )
    return "queued"


async def _send_private_emails(items: list[dict]) -> None:
    loop = asyncio.get_running_loop()
    slots = _slots.setdefault(loop, asyncio.Semaphore(2))
    for item in items:
        async with slots:
            try:
                async with SessionLocal() as session:
                    switches = await load_switches(session)
                provider = providers.email_provider()
                if not switches["email"] or not provider.configured():
                    log.info("notify: %s email skipped at send time", item["kind"])
                    continue
                await provider.send(item["to"], item["subject"], item["body"])
                log.info("notify: %s email sent", item["kind"])
            except ProviderError as exc:
                log.warning("notify: %s email failed: %s", item["kind"], exc)
            except Exception:  # noqa: BLE001 — a background send must never crash the app
                log.exception("notify: %s email crashed", item["kind"])


# --- after-commit dispatch -------------------------------------------------------------

_QUEUE_KEY = "notification_deliveries"
_PRIVATE_KEY = "notification_private_emails"
_inflight: set[asyncio.Task] = set()
# at most two provider calls hold a pooled connection at once (pool is 5 + 5)
_slots: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = WeakKeyDictionary()


@event.listens_for(Session, "after_commit")
def _dispatch_after_commit(sync_session: Session) -> None:
    if sync_session.in_nested_transaction():
        return  # a SAVEPOINT release: nothing is durable until the outer COMMIT
    ids = sync_session.info.pop(_QUEUE_KEY, None)
    private = sync_session.info.pop(_PRIVATE_KEY, None)
    if not ids and not private:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # sync context: outbox rows stay `pending` for a later dispatch/sweeper;
        # private emails are dropped (the user can ask again)
        log.warning("notify: no running loop; nothing dispatched")
        return
    for job in (
        dispatch_deliveries(ids) if ids else None,
        _send_private_emails(private) if private else None,
    ):
        if job is not None:
            task = loop.create_task(job)
            _inflight.add(task)
            task.add_done_callback(_inflight.discard)


@event.listens_for(Session, "after_transaction_end")
def _drop_after_rollback(sync_session: Session, transaction) -> None:
    # after_commit has already taken the queue on success; anything left when
    # the outer transaction ends was rolled back with the notification rows
    if transaction.parent is None:
        sync_session.info.pop(_QUEUE_KEY, None)
        sync_session.info.pop(_PRIVATE_KEY, None)


async def drain() -> None:
    """Wait for in-flight background dispatches (tests, graceful shutdown)."""
    while _inflight:
        await asyncio.gather(*list(_inflight), return_exceptions=True)


async def dispatch_deliveries(delivery_ids: list[str]) -> None:
    """Send the given outbox rows. Safe to re-run: `sent`/`skipped` rows are left alone."""
    loop = asyncio.get_running_loop()
    slots = _slots.setdefault(loop, asyncio.Semaphore(2))
    for delivery_id in delivery_ids:
        async with slots:
            try:
                await _dispatch_one(delivery_id)
            except Exception:  # noqa: BLE001 — a background send must never crash the app
                log.exception("notify: delivery %s crashed", delivery_id)


async def _dispatch_one(delivery_id: str) -> None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT d.id, d.channel, d.recipient, n.title, n.message "
                    "FROM public.notification_deliveries d "
                    "JOIN public.notifications n ON n.id = d.notification_id "
                    "WHERE d.id = CAST(:did AS uuid) AND d.status IN ('pending', 'failed') "
                    "FOR UPDATE OF d SKIP LOCKED"
                ),
                {"did": delivery_id},
            )
        ).mappings().first()
        if row is None:
            return  # already sent/skipped, or another sender holds the row

        channel = row["channel"]
        switches = await load_switches(session)
        provider = providers.sms_provider() if channel == "sms" else providers.email_provider()
        attempted = 0
        if not switches[channel]:
            status, error = "skipped", "channel_disabled"  # switched off since the event
        elif not provider.configured():
            status, error = "skipped", "provider_not_configured"
        else:
            attempted = 1
            try:
                if channel == "sms":
                    await provider.send(row["recipient"], f"{BRAND}\n{row['message']}")
                else:
                    await provider.send(
                        row["recipient"],
                        f"{row['title']} — {BRAND}",
                        f"{row['message']}\n\n{BRAND}",
                    )
                status, error = "sent", None
            except ProviderError as exc:
                status, error = "failed", str(exc)
                log.warning("notify: %s delivery %s failed: %s", channel, delivery_id, exc)
            except Exception as exc:  # noqa: BLE001
                status, error = "failed", f"{type(exc).__name__}"
                log.exception("notify: %s delivery %s crashed", channel, delivery_id)

        await session.execute(
            text(
                "UPDATE public.notification_deliveries SET status = :status, "
                "last_error = :error, provider = :provider, attempts = attempts + :tried, "
                "updated_at = now() WHERE id = CAST(:did AS uuid)"
            ),
            {
                "status": status,
                "error": error,
                "provider": provider.name,
                "tried": attempted,
                "did": delivery_id,
            },
        )
        await session.commit()
