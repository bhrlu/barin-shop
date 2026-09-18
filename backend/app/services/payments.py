"""Zarinpal payment gateway (v4 REST) with a simulation fallback.

Flow
----
1. POST /payments/start        → creates a pending `payments` row, calls
   payment/request.json, returns the StartPay redirect URL.
2. User pays on the gateway; gateway redirects to GET /payments/zarinpal/callback.
3. Callback verifies via payment/verify.json, marks order paid / payment
   succeeded and redirects the shopper to the frontend payment page.

If no real merchant id is configured, the module runs in simulation mode so the
flow is testable end-to-end without credentials (mirrors the current frontend
simulator, but with real DB records).

Status conventions match the existing Supabase data:
  orders.payment_status: unpaid | paid | refunded
  orders.status:         pending | processing | shipped | delivered | cancelled
  payments.status:       pending | succeeded | failed
  references:            SND-{order_number}-{6 digits}
"""

import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = logging.getLogger(__name__)

REQUEST_ENDPOINT = "/pg/v4/payment/request.json"
VERIFY_ENDPOINT = "/pg/v4/payment/verify.json"
SUCCESS_CODES = {100}  # 100 = verified, 101 = already verified (handled separately)
ALREADY_VERIFIED = 101


class PaymentError(Exception):
    def __init__(self, code: str, message_fa: str):
        self.code = code
        self.message_fa = message_fa
        super().__init__(message_fa)


@dataclass(frozen=True)
class PaymentStart:
    authority: str
    redirect_url: str
    amount: int  # tomans


@dataclass(frozen=True)
class PaymentVerify:
    status: str  # "paid" | "already_paid" | "failed"
    reference: str | None
    amount: int
    # Returned so callers do not have to look the payment up again: `reference`
    # stops being the authority once the row is finalized.
    order_id: str | None = None


def _base_url() -> str:
    return (
        "https://sandbox.zarinpal.com"
        if settings.zarinpal_sandbox
        else "https://payment.zarinpal.com"
    )


def _api_base() -> str:
    return (
        "https://sandbox.zarinpal.com"
        if settings.zarinpal_sandbox
        else "https://api.zarinpal.com"
    )


def _simulation_mode() -> bool:
    return (
        not settings.zarinpal_merchant_id
        or settings.zarinpal_merchant_id == "00000000-0000-0000-0000-000000000000"
    )


def tracking_code(order_number: str, order_id: str) -> str:
    return f"SND-{order_number}-{order_id[:6].upper()}"


def fake_reference(order_number: str) -> str:
    return f"SND-{order_number}-{secrets.randbelow(900_000) + 100_000}"


# --- gateway calls -------------------------------------------------------------


async def gateway_request_payment(amount_tomans: int, description: str) -> str:
    """Returns the payment Authority from Zarinpal (or raises PaymentError)."""
    payload = {
        "merchant_id": settings.zarinpal_merchant_id,
        "amount": amount_tomans,  # Zarinpal v4 expects Toman
        "callback_url": f"{settings.public_base_url}/payments/zarinpal/callback",
        "description": description,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(_api_base() + REQUEST_ENDPOINT, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as exc:
        log.warning("zarinpal request failed: %s", exc)
        raise PaymentError(
            "gateway_unreachable", "درگاه پرداخت در دسترس نیست؛ دوباره تلاش کنید"
        ) from exc

    data = body.get("data") or {}
    if data.get("code") not in SUCCESS_CODES or not data.get("authority"):
        errors = body.get("errors") or {}
        log.warning("zarinpal request rejected: %s", errors)
        raise PaymentError("rejected", "درگاه پرداخت درخواست را نپذیرفت")

    return str(data["authority"])


async def gateway_verify_payment(authority: str, amount_tomans: int) -> PaymentVerify:
    payload = {
        "merchant_id": settings.zarinpal_merchant_id,
        "amount": amount_tomans,
        "authority": authority,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(_api_base() + VERIFY_ENDPOINT, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as exc:
        log.warning("zarinpal verify failed: %s", exc)
        raise PaymentError(
            "gateway_unreachable", "بررسی پرداخت ناموفق بود؛ بعداً تلاش کنید"
        ) from exc

    data = body.get("data") or {}
    code = data.get("code")
    ref_id = data.get("ref_id")

    if code in SUCCESS_CODES:
        return PaymentVerify(status="paid", reference=str(ref_id), amount=amount_tomans)
    if code == ALREADY_VERIFIED:
        return PaymentVerify(status="already_paid", reference=str(ref_id), amount=amount_tomans)
    return PaymentVerify(status="failed", reference=None, amount=amount_tomans)


# --- high-level operations -------------------------------------------------------


async def start_payment(
    session: AsyncSession, order_id: UUID, user_id: UUID
) -> PaymentStart:
    row = (
        await session.execute(
            text(
                "SELECT id, order_number, user_id, total, payment_status "
                "FROM public.orders WHERE id = :oid"
            ),
            {"oid": str(order_id)},
        )
    ).mappings().first()

    if row is None or row["user_id"] != user_id:
        raise PaymentError("not_found", "سفارش پیدا نشد")
    if row["payment_status"] == "paid":
        raise PaymentError("already_paid", "این سفارش قبلاً پرداخت شده است")

    amount = int(row["total"])

    if _simulation_mode():
        authority = f"SIM{secrets.token_hex(12).upper()}"
    else:
        authority = await gateway_request_payment(
            amount, f"پرداخت سفارش {row['order_number']} – ساندِه"
        )

    # remember the session: pending payments row keyed by authority
    await session.execute(
        text(
            "INSERT INTO public.payments (order_id, user_id, amount, method, status, reference) "
            "VALUES (:oid, :uid, :amount, 'online', 'pending', :authority)"
        ),
        {"oid": str(order_id), "uid": str(user_id), "amount": amount, "authority": authority},
    )

    return PaymentStart(
        authority=authority,
        redirect_url=f"{_base_url()}/pg/StartPay/{authority}",
        amount=amount,
    )


async def verify_and_finalize(session: AsyncSession, authority: str, ok: bool) -> PaymentVerify:
    """Called from the gateway callback. Finalizes order + payment rows."""
    pay = (
        await session.execute(
            text(
                "SELECT id, order_id, user_id, amount, status FROM public.payments "
                "WHERE reference = :authority AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"authority": authority},
        )
    ).mappings().first()

    if pay is None:
        raise PaymentError("unknown_session", "جلسه پرداخت پیدا نشد")

    order = (
        await session.execute(
            text("SELECT id, order_number, payment_status FROM public.orders WHERE id = :oid"),
            {"oid": str(pay["order_id"])},
        )
    ).mappings().first()
    if order is None:
        raise PaymentError("not_found", "سفارش پیدا نشد")

    amount = int(pay["amount"])

    order_id = str(pay["order_id"])

    if order["payment_status"] == "paid":
        await session.execute(
            text("UPDATE public.payments SET status = 'failed' WHERE id = :pid"),
            {"pid": str(pay["id"])},
        )
        return PaymentVerify(
            status="already_paid", reference=None, amount=amount, order_id=order_id
        )

    if not ok:
        await session.execute(
            text("UPDATE public.payments SET status = 'failed' WHERE id = :pid"),
            {"pid": str(pay["id"])},
        )
        return PaymentVerify(
            status="failed", reference=None, amount=amount, order_id=order_id
        )

    if _simulation_mode():
        reference = fake_reference(order["order_number"])
    else:
        verify = await gateway_verify_payment(authority, amount)
        if verify.status == "failed":
            await session.execute(
                text("UPDATE public.payments SET status = 'failed' WHERE id = :pid"),
                {"pid": str(pay["id"])},
            )
            return PaymentVerify(
                status="failed", reference=None, amount=amount, order_id=order_id
            )
        if verify.status == "already_paid":
            return PaymentVerify(
                status="already_paid",
                reference=verify.reference,
                amount=amount,
                order_id=order_id,
            )
        reference = verify.reference or fake_reference(order["order_number"])

    await session.execute(
        text(
            "UPDATE public.orders SET payment_status = 'paid', status = 'processing' "
            "WHERE id = :oid"
        ),
        {"oid": str(pay["order_id"])},
    )
    await session.execute(
        text(
            "UPDATE public.payments SET status = 'succeeded', reference = :ref WHERE id = :pid"
        ),
        {"pid": str(pay["id"]), "ref": reference},
    )
    return PaymentVerify(
        status="paid", reference=reference, amount=amount, order_id=order_id
    )


def frontend_redirect(order_id: str, result: PaymentVerify) -> str:
    """Send the shopper back to the existing frontend payment page."""
    qs = urlencode({"verify": result.status, "ref": result.reference or ""})
    return f"{settings.frontend_url}/payment/{order_id}?{qs}"
