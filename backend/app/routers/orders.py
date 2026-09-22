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

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser, DbSession, StaffOrders, StaffRefunds
from app.services.audit import record_audit
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

# Spec [BE-05]: an order may only move forward through fulfilment, and a
# cancelled or delivered order is terminal. Keys/values are the existing status
# strings (Rule 4 — the vocabulary itself is unchanged).
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "shipped", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


async def _restore_stock(session, order_id: str) -> None:
    """Spec [BE-05]: give the reserved units back when an order is cancelled.

    Checkout decremented `products.stock` per line, so cancellation adds the same
    quantities back. Called only on the pending/processing/shipped → cancelled
    transition, so a repeated cancel can never inflate stock.
    """
    await session.execute(
        text(
            "UPDATE public.products p SET stock = p.stock + i.qty FROM ("
            "  SELECT product_id, SUM(quantity) AS qty FROM public.order_items "
            "  WHERE order_id = CAST(:oid AS uuid) AND product_id IS NOT NULL "
            "  GROUP BY product_id"
            ") i WHERE p.id = i.product_id"
        ),
        {"oid": str(order_id)},
    )

_ORDER_SELECT = (
    "SELECT o.id, o.order_number, o.user_id, o.status, o.payment_status, o.payment_method, "
    "o.subtotal, o.discount, o.shipping, o.total, o.shipping_address, o.note, "
    "o.tracking_code, o.created_at, "
    "COALESCE(json_agg(json_build_object("
    "'id', i.id, 'order_id', i.order_id, 'product_id', i.product_id, 'name', i.name, "
    "'price', i.price, 'size', i.size, 'color', i.color, 'image', i.image, "
    "'quantity', i.quantity)) FILTER (WHERE i.id IS NOT NULL), '[]') AS items "
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
async def my_orders(user: CurrentUser, session: DbSession) -> list[dict]:
    rows = (
        await session.execute(
            text(
                _ORDER_SELECT
                + " WHERE o.user_id = CAST(:uid AS uuid) GROUP BY o.id ORDER BY o.created_at DESC"
            ),
            {"uid": str(user.id)},
        )
    ).mappings().all()
    return [_order_row(r) for r in rows]


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

    # capture the previous values so the audit entry shows old → new
    before = await _fetch_order(session, str(order_id), admin=True)
    if before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")

    # spec [BE-05]: reject impossible transitions (a cancelled order can never
    # become shipped); re-setting the same status stays a no-op success
    if body.status and body.status != before["status"]:
        if body.status not in _STATUS_TRANSITIONS.get(before["status"], set()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"تغییر وضعیت از «{before['status']}» به «{body.status}» مجاز نیست",
            )

    sets = []
    params: dict = {"oid": str(order_id)}
    if body.status:
        sets.append("status = :status")
        params["status"] = body.status
    if body.payment_status:
        sets.append("payment_status = :pstatus")
        params["pstatus"] = body.payment_status
    if body.tracking_code is not None:
        # empty string clears the code, mirroring PATCH /addresses semantics
        sets.append("tracking_code = :tracking")
        params["tracking"] = body.tracking_code.strip() or None
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    # spec [BE-05]: cancelling releases the reserved units back to the catalog
    if body.status == "cancelled" and before["status"] != "cancelled":
        await _restore_stock(session, str(order_id))

    # perform the update first, then re-select
    await session.execute(
        text(f"UPDATE public.orders SET {', '.join(sets)} WHERE id = CAST(:oid AS uuid)"),
        params,
    )
    order = await _fetch_order(session, str(order_id), admin=True)
    if order is None:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")

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

    await session.commit()
    return order


@router.post("/orders/{order_id}/cancel", response_model=CancelOut)
async def cancel_order(order_id: UUID, user: CurrentUser, session: DbSession) -> CancelOut:
    order = await _fetch_order(session, str(order_id), user_id=user.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")
    if order["status"] == "cancelled":
        return CancelOut(ok=True, order_number=order["order_number"], refund_eligible=False)
    if order["status"] in ("shipped", "delivered"):
        raise HTTPException(status.HTTP_409_CONFLICT, "سفارش ارسال شده و امکان لغو ندارد")

    await _restore_stock(session, str(order_id))
    await session.execute(
        text("UPDATE public.orders SET status = 'cancelled' WHERE id = CAST(:oid AS uuid)"),
        {"oid": str(order_id)},
    )
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
    except Exception as exc:
        await session.rollback()
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
    await session.commit()
    return PaymentCompleteOut(ok=paid, order_number=order["order_number"], reference=reference)
