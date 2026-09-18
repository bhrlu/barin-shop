"""Payment endpoints: start a Zarinpal session and handle the gateway callback.

The callback is called by the gateway (unauthenticated), so it uses the DB
session dependency directly instead of the CurrentUser dependency.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, DbSession
from app.db import get_session
from app.schemas import PaymentRequest, PaymentStartOut, PaymentVerifyOut
from app.services.payments import (
    PaymentError,
    frontend_redirect,
    start_payment,
    verify_and_finalize,
)

GatewaySession = Annotated[AsyncSession, Depends(get_session)]

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/start", response_model=PaymentStartOut)
async def start(body: PaymentRequest, user: CurrentUser, session: DbSession) -> PaymentStartOut:
    try:
        started = await start_payment(session, body.order_id, user.id)
    except PaymentError as exc:
        if exc.code in ("not_found", "unknown_session"):
            http_code = status.HTTP_404_NOT_FOUND
        elif exc.code == "already_paid":
            http_code = status.HTTP_409_CONFLICT
        else:
            http_code = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(http_code, exc.message_fa, detail={"code": exc.code}) from exc
    return PaymentStartOut(
        authority=started.authority,
        redirect_url=started.redirect_url,
        amount=started.amount,
    )


@router.get("/zarinpal/callback")
async def zarinpal_callback(
    authority: str = Query(...),
    ok: bool = Query(default=True),
    session: GatewaySession = None,
) -> RedirectResponse:  # noqa: B008
    """Gateway redirects here after the payer returns.

    `ok=false` simulates a cancelled/failed payment (Zarinpal signals this via
    Status=NOK; the adapter in main maps that before calling this handler).
    """
    try:
        result = await verify_and_finalize(session, authority, ok=ok)
    except PaymentError as exc:
        log.warning("payment callback failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message_fa) from exc

    order_id = None
    # find the order for the redirect target
    from sqlalchemy import text

    row = (
        await session.execute(
            text(
                "SELECT order_id FROM public.payments WHERE reference = :authority "
                "AND status IN ('succeeded','failed') ORDER BY created_at DESC LIMIT 1"
            ),
            {"authority": authority},
        )
    ).first()
    if row is not None:
        order_id = str(row[0])

    if order_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش پیدا نشد")

    return RedirectResponse(url=frontend_redirect(order_id, result), status_code=303)


@router.post("/verify", response_model=PaymentVerifyOut)
async def manual_verify(
    authority: str, user: CurrentUser, session: DbSession
) -> PaymentVerifyOut:
    """Manual verification for polling clients (e.g. mobile in-app browser)."""
    try:
        result = await verify_and_finalize(session, authority, ok=True)
    except PaymentError as exc:
        if exc.code in ("not_found", "unknown_session"):
            http_code = status.HTTP_404_NOT_FOUND
        else:
            http_code = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(http_code, exc.message_fa, detail={"code": exc.code}) from exc
    return PaymentVerifyOut(
        status=result.status, reference=result.reference, amount=result.amount
    )
