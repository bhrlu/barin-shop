"""Checkout endpoints.

POST /checkout  — creates a pending order with transactional stock decrement
                  and optional coupon. Returns the order summary; the caller
                  then starts a payment session for it.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser, DbSession
from app.schemas import CheckoutRequest, OrderCreated
from app.services.checkout import CheckoutError, create_order

log = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])


@router.post("/checkout", response_model=OrderCreated)
async def checkout(body: CheckoutRequest, user: CurrentUser, session: DbSession) -> OrderCreated:
    lines = [line.model_dump() for line in body.lines]
    address = body.address.model_dump()

    try:
        order = await create_order(
            session,
            user_id=user.id,
            lines=lines,
            address=address,
            coupon_code=body.coupon_code,
        )
    except CheckoutError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if exc.code == "stock_conflict"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code,
            exc.message_fa,
            detail={"code": exc.code, "issues": exc.issues},
        ) from exc

    return OrderCreated(
        order_id=order["order_id"],
        order_number=order["order_number"],
        subtotal=order["subtotal"],
        discount=order["discount"],
        shipping=order["shipping"],
        total=order["total"],
        coupon_applied=order["coupon_applied"],
    )
