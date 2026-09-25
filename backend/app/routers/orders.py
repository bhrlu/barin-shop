"""Order endpoints for customers + admin.

- GET /orders            — the caller's orders with items
- GET /orders/{id}       — one order (owner or admin)
- PATCH /orders/{id}     — admin status updates + shipment tracking code
- POST /orders/{id}/cancel        — customer cancel (pre-shipment only)
- POST /orders/{id}/refunds       — customer refund request (cancelled+paid)
- PATCH /refunds/{requestId}      — admin resolves a refund request
- GET /orders/{id}/payment-session — simulated gateway session data
- POST /orders/{id}/payment-complete — simulated gateway callback
"""

import logging
import random
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, DbSession, StaffOrders, StaffRefunds
from app.services.audit import record_audit
from app.services.db_errors import is_unique_violation
from app.services.notifications import notify_order_event, notify_refund_event
from app.services.order_lifecycle import (
    CancelError,
    IllegalTransition,
    assert_transition,
    cancel_order_tx,
)
from app.services.pagination import clamp_page_size, count_rows, envelope
from app.services.payments import simulation_mode
from app.services.roles import has_capability

log = logging.getLogger(__name__)
router = APIRouter(tags=["orders"])


class OrderPatch(BaseModel):
    status: str | None = None
    payment_status: str | None = None
    tracking_code: str | None = Field(default=None, max_length=60)


class CancelOut(BaseModel):
    ok: bool
    order_number: str
    refund_eligible: bool


class RefundRequestIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class RefundResolveIn(BaseModel):
    status: str  # approved | rejected | refunded
    admin_note: str | None = Field(default=None, max_length=500)
    # spec [BE-03]/[FE-06]: the Paya/Satna code is required by the UI when
    # settling; the API accepts it for any resolution and stores what it gets
    bank_tracking_code: str | None = Field(default=None, max_length=60)


class RefundRequestOut(BaseModel):
    id: UUID
    order_id: UUID
    amount: int
    status: str


class PaymentSessionOut(BaseModel):
    order_id: str
    order_number: str
    total: int
    payment_status: str
    # the simulated gateway's session code, unrelated to the shipment tracking code
    tracking_code: str


class PaymentCompleteIn(BaseModel):
    outcome: str  # success | failure


class PaymentCompleteOut(BaseModel):
    ok: bool
    order_number: str
    reference: str | None


_ALLOWED_STATUS = {"pending", "processing", "shipped", "delivered", "cancelled"}
_ALLOWED_PAYMENT_STATUS = {"unpaid", "paid", "refunded"}

_ORDER_SELECT = (
    "SELECT o.id, o.order_number, o.user_id, o.status, o.payment_status, o.payment_method, "
    "o.subtotal, o.discount, o.shipping, o.total, o.shipping_address, o.note, "
    "o.tracking_code, o.created_at, "
    "COALESCE(json_agg(json_build_object("
    "'id', i.id, 'order_id', i.order_id, 'product_id', i.product_id, 'name', i.name, "
    "'price', i.price, 'size', i.size, 'color', i.color, 'image', i.image, "
    "'quantity', i.quantity, 'is_preorder', COALESCE(i.is_preorder, false))) "
    "FILTER (WHERE i.id IS NOT NULL), '[]') AS items "
    "FROM public.orders o LEFT JOIN public.order_items i ON i.order_id = o.id"
)


def _order_row(row) -> dict:
    d = dict(row)
    d["shipping_address"] = d.get("shipping_address") or {}
    return d


async def _fetch_order(session, order_id: str, user_id=None, admin: bool = False):
    sql = _ORDER_SELECT + " WHERE o.id = CAST(:oid AS uuid)"
    params: dict = {"oid": str(order_id)}
    if not admin:
        sql += " AND o.user_id = CAST(:uid AS uuid)"
        params["uid"] = str(user_id)
    sql += " GROUP BY o.id"
    row = (await session.execute(text(sql), params)).mappings().first()
    return dict(row) if row else None


@router.get("/orders")
async def my_orders(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
) -> list[dict] | dict:
    """The signed-in customer's orders; envelope when `page` is given."""
    base_sql = _ORDER_SELECT + " WHERE o.user_id = CAST(:uid AS uuid) GROUP BY o.id"
    params: dict = {"uid": str(user.id)}
    page, page_size = clamp_page_size(page, page_size, default_size=10)
    sql = base_sql + " ORDER BY o.created_at DESC"
    total = 0
    if page > 0:
        total = await count_rows(session, base_sql, params)
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [_order_row(r) for r in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, user: CurrentUser, session: DbSession) -> dict:
    """The caller's own order; staff with the `orders` capability may read any."""
    staff = has_capability(user.roles, "orders")
    order = await _fetch_order(session, str(order_id), user_id=user.id, admin=staff)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    return order


@router.patch("/orders/{order_id}")
async def patch_order(
    order_id: UUID, body: OrderPatch, session: DbSession, user: StaffOrders
) -> dict:
    if body.status and body.status not in _ALLOWED_STATUS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت نامعتبر است")
    if body.payment_status and body.payment_status not in _ALLOWED_PAYMENT_STATUS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت پرداخت نامعتبر است")
    if not (body.status or body.payment_status or body.tracking_code is not None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    # capture the previous values: the state machine needs the old status, and
    # the audit entries show old → new (B5.1)
    before = await _fetch_order(session, str(order_id), admin=True)
    if before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")

    # state machine (spec [BE-05]): reject illegal moves before touching the row
    if body.status:
        try:
            assert_transition(before["status"], body.status)
        except IllegalTransition as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"تغییر وضعیت از «{exc.old}» به «{exc.new}» مجاز نیست",
            ) from exc

    sets = []
    params: dict = {"oid": str(order_id)}
    did_cancel = False
    if body.status == "cancelled":
        # The admin status select offers «لغو شده», so PATCH must behave exactly
        # like POST /cancel: cancel_order_tx flips the status AND restores the
        # stock in the same transaction (spec [BE-05]).
        try:
            await cancel_order_tx(session, str(order_id), before["status"], user.id)
        except CancelError as exc:  # defensive: the transition map already gated it
            raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
        did_cancel = True
    elif body.status:
        sets.append("status = :status")
        params["status"] = body.status
    if body.payment_status:
        sets.append("payment_status = :pstatus")
        params["pstatus"] = body.payment_status
    if body.tracking_code is not None:
        # empty string clears the code, mirroring PATCH /addresses semantics
        sets.append("tracking_code = :tracking")
        params["tracking"] = body.tracking_code.strip() or None

    if sets:
        # perform the update first, then re-select
        await session.execute(
            text(f"UPDATE public.orders SET {', '.join(sets)} WHERE id = CAST(:oid AS uuid)"),
            params,
        )
    elif not did_cancel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")
    order = await _fetch_order(session, str(order_id), admin=True)

    # audit: one entry per changed facet (B5.1)
    if before is not None:
        changed = {
            k: (before.get(k), order.get(k))
            for k in ("status", "payment_status", "tracking_code")
            if before.get(k) != order.get(k)
        }
        if "status" in changed:
            await record_audit(
                session,
                admin_id=user.id,
                action="update_order_status",
                entity_type="order",
                entity_id=str(order_id),
                old_values={"status": changed["status"][0]},
                new_values={"status": changed["status"][1]},
            )
        if "payment_status" in changed:
            await record_audit(
                session,
                admin_id=user.id,
                action="update_order_payment_status",
                entity_type="order",
                entity_id=str(order_id),
                old_values={"payment_status": changed["payment_status"][0]},
                new_values={"payment_status": changed["payment_status"][1]},
            )
        if "tracking_code" in changed:
            await record_audit(
                session,
                admin_id=user.id,
                action="update_order_tracking_code",
                entity_type="order",
                entity_id=str(order_id),
                old_values={"tracking_code": changed["tracking_code"][0]},
                new_values={"tracking_code": changed["tracking_code"][1]},
            )

        # B2.1: tell the customer at the transition itself (a cancel notifies
        # from cancel_order_tx); repeats are deduped by the notification service
        if "status" in changed and order["status"] == "shipped":
            await notify_order_event(session, str(order_id), "shipped")
        if "payment_status" in changed and order["payment_status"] == "paid":
            await notify_order_event(session, str(order_id), "paid")

    await session.commit()
    return order


@router.post("/orders/{order_id}/cancel", response_model=CancelOut)
async def cancel_order(order_id: UUID, user: CurrentUser, session: DbSession) -> CancelOut:
    order = await _fetch_order(session, str(order_id), user_id=user.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    if order["status"] == "cancelled":
        return CancelOut(ok=True, order_number=order["order_number"], refund_eligible=False)
    try:
        # flip + stock restore in ONE transaction (spec [BE-05]) — checkout's
        # decrement is transactional, so the give-back must be too
        await cancel_order_tx(session, str(order_id), order["status"], user.id)
    except CancelError as exc:
        await session.rollback()
        if exc.already_cancelled:
            # lost a race with another cancel (B6.19): same answer as the check above
            return CancelOut(ok=True, order_number=order["order_number"], refund_eligible=False)
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc

    await record_audit(
        session,
        admin_id=user.id,
        action="cancel_order",
        entity_type="order",
        entity_id=str(order_id),
        old_values={"status": order["status"]},
        new_values={"status": "cancelled"},
    )
    await session.commit()
    return CancelOut(
        ok=True,
        order_number=order["order_number"],
        refund_eligible=order["payment_status"] == "paid",
    )


# the SQLSTATE 23505 check moved to app/services/db_errors.py (B6.9a); the old
# name stays importable for the B6.9 tests
_is_unique_violation = is_unique_violation


@router.post("/orders/{order_id}/refunds", response_model=RefundRequestOut, status_code=201)
async def request_refund(
    order_id: UUID, body: RefundRequestIn, user: CurrentUser, session: DbSession
) -> RefundRequestOut:
    order = await _fetch_order(session, str(order_id), user_id=user.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    if order["status"] != "cancelled" or order["payment_status"] != "paid":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "فقط برای سفارش‌های لغوشده و پرداخت‌شده می‌توان بازپرداخت درخواست کرد",
        )

    try:
        row = (
            await session.execute(
                text(
                    "INSERT INTO public.refund_requests "
                    "(order_id, user_id, amount, reason, status) "
                    "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, :reason, 'pending') "
                    "RETURNING id, order_id, amount, status"
                ),
                {
                    "oid": str(order_id),
                    "uid": str(user.id),
                    "amount": order["total"],
                    "reason": body.reason,
                },
            )
        ).mappings().first()
        await session.commit()
    except IntegrityError as exc:
        # `refund_requests` is UNIQUE (order_id): a second request for the same
        # order is the expected duplicate, answered with 409 (B6.9). Any other
        # integrity failure (a foreign key, a check constraint) is a real bug and
        # must not be disguised as "already requested" — re-raise it so the
        # 500 and the traceback survive.
        await session.rollback()
        if not _is_unique_violation(exc):
            log.exception("refund request failed with an unexpected integrity error")
            raise
        raise HTTPException(
            status.HTTP_409_CONFLICT, "برای این سفارش قبلاً درخواست بازپرداخت ثبت شده است"
        ) from exc
    return RefundRequestOut(**dict(row))


@router.patch("/refunds/{request_id}")
async def resolve_refund(
    request_id: UUID, body: RefundResolveIn, user: StaffRefunds, session: DbSession
) -> dict:
    if body.status not in ("approved", "rejected", "refunded"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت نامعتبر است")

    # [FE-06]: settling without the Paya/Satna code leaves the refund
    # untraceable at the bank; the UI enforces this too
    if body.status == "refunded" and not (body.bank_tracking_code or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "برای ثبت بازگشت وجه، کد رهگیری بانکی الزامی است",
        )

    # A settled refund is terminal: re-running the settlement used to insert a
    # second `refund` payment row and flip the order again (double accounting).
    current = (
        await session.execute(
            text(
                "SELECT status FROM public.refund_requests WHERE id = CAST(:rid AS uuid)"
            ),
            {"rid": str(request_id)},
        )
    ).first()
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پیدا نشد")
    previous_status = current[0]
    if previous_status == "refunded":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "این درخواست قبلاً تسویه شده است"
        )

    row = (
        await session.execute(
            text(
                "UPDATE public.refund_requests SET status = :status, admin_note = :note, "
                "bank_tracking_code = COALESCE(:bank, bank_tracking_code), "
                "resolved_by = CAST(:admin AS uuid), resolved_at = now() "
                "WHERE id = CAST(:rid AS uuid) "
                "RETURNING id, order_id, user_id, amount"
            ),
            {
                "rid": str(request_id),
                "status": body.status,
                "note": body.admin_note,
                "bank": (body.bank_tracking_code or "").strip() or None,
                "admin": str(user.id),
            },
        )
    ).mappings().first()
    if row is None:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پیدا نشد")

    if body.status == "refunded":
        await session.execute(
            text("UPDATE public.orders SET payment_status = 'refunded' WHERE id = :oid"),
            {"oid": str(row["order_id"])},
        )
        await session.execute(
            text(
                "INSERT INTO public.payments "
                "(order_id, user_id, amount, method, status, reference) "
                "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, "
                "        'refund', 'refunded', :ref)"
            ),
            {
                "oid": str(row["order_id"]),
                "uid": str(row["user_id"]),
                "amount": row["amount"],
                "ref": f"RFD-{str(row['id'])[:8].upper()}",
            },
        )

    # B2.1: approval and settlement reach the claimant; a rejection does not (D2)
    if body.status == "approved":
        await notify_refund_event(session, str(row["id"]), "approved")
    elif body.status == "refunded":
        await notify_refund_event(session, str(row["id"]), "settled")

    await record_audit(
        session,
        admin_id=user.id,
        action="resolve_refund",
        entity_type="order",
        entity_id=str(row["order_id"]),
        old_values={"refund_status": previous_status},
        new_values={
            "refund_status": body.status,
            "bank_tracking_code": (body.bank_tracking_code or "").strip() or None,
            "admin_note": body.admin_note,
        },
    )
    await session.commit()
    return {"ok": True}


@router.get("/orders/{order_id}/payment-session", response_model=PaymentSessionOut)
async def payment_session(
    order_id: UUID, user: CurrentUser, session: DbSession
) -> PaymentSessionOut:
    order = await _fetch_order(session, str(order_id), user_id=user.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    tracking = f"SND-{order['order_number']}-{str(order['id'])[:6].upper()}"
    return PaymentSessionOut(
        order_id=str(order["id"]),
        order_number=order["order_number"],
        total=order["total"],
        payment_status=order["payment_status"],
        tracking_code=tracking,
    )


@router.post("/orders/{order_id}/payment-complete", response_model=PaymentCompleteOut)
async def payment_complete(
    order_id: UUID, body: PaymentCompleteIn, user: CurrentUser, session: DbSession
) -> PaymentCompleteOut:
    if body.outcome not in ("success", "failure"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "نتیجه نامعتبر است")

    # This endpoint IS the simulated gateway: it marks an order paid on the
    # client's word alone. With a real merchant id configured that would be free
    # goods, so it is refused and the caller must go through /payments/*.
    if not simulation_mode():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "پرداخت باید از طریق درگاه انجام شود",
        )

    order = await _fetch_order(session, str(order_id), user_id=user.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    if order["payment_status"] == "paid":
        return PaymentCompleteOut(ok=True, order_number=order["order_number"], reference=None)

    paid = body.outcome == "success"
    reference = f"SND-{order['order_number']}-{random.randint(100000, 999999)}"

    await session.execute(
        text(
            "UPDATE public.orders SET payment_status = :ps, status = :st "
            "WHERE id = CAST(:oid AS uuid)"
        ),
        {
            "oid": str(order_id),
            "ps": "paid" if paid else "unpaid",
            "st": "processing" if paid else "pending",
        },
    )
    await session.execute(
        text(
            "INSERT INTO public.payments (order_id, user_id, amount, method, status, reference) "
            "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, 'online', :status, :ref)"
        ),
        {
            "oid": str(order_id),
            "uid": str(user.id),
            "amount": order["total"],
            "status": "succeeded" if paid else "failed",
            "ref": reference,
        },
    )
    if paid:
        await notify_order_event(session, str(order_id), "paid")
    await session.commit()
    return PaymentCompleteOut(ok=paid, order_number=order["order_number"], reference=reference)
