"""Coupon validation and transactional redemption.

A coupon is either percent-off or amount-off (never both). Validation checks
active flag, time window, min subtotal, global usage cap and per-user cap.
Redemption re-checks everything and increments used_count atomically with a
row-level lock (FOR UPDATE) inside the checkout transaction.
"""

import secrets
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coupon

COUPON_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code(prefix: str = "SANDE", length: int = 6) -> str:
    body = "".join(secrets.choice(COUPON_ALPHABET) for _ in range(length))
    return f"{prefix}{body}"


class CouponError(Exception):
    def __init__(self, code: str, message_fa: str):
        self.code = code
        self.message_fa = message_fa
        super().__init__(message_fa)


def compute_discount(coupon: Coupon, subtotal: int) -> int:
    if coupon.percent_off is not None:
        d = subtotal * coupon.percent_off // 100
    elif coupon.amount_off is not None:
        d = coupon.amount_off
    else:  # defensive: malformed row
        d = 0
    return max(0, min(d, subtotal))


async def get_coupon_for_update(session: AsyncSession, code: str) -> Coupon | None:
    row = (
        await session.execute(
            text("SELECT * FROM public.coupons WHERE code = :code FOR UPDATE"),
            {"code": code},
        )
    ).mappings().first()
    if row is None:
        return None
    return Coupon(**row)


def validate_coupon(coupon: Coupon, subtotal: int, user_id: UUID, prior_uses: int) -> int:
    """Return discount amount or raise CouponError (messages in Persian, like the UI)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    starts = coupon.starts_at.replace(tzinfo=None) if coupon.starts_at else None
    expires = coupon.expires_at.replace(tzinfo=None) if coupon.expires_at else None

    if not coupon.active:
        raise CouponError("inactive", "این کد تخفیف غیرفعال است")
    if starts and now < starts:
        raise CouponError("not_started", "این کد تخفیف هنوز فعال نشده است")
    if expires and now > expires:
        raise CouponError("expired", "این کد تخفیف منقضی شده است")
    if subtotal < coupon.min_subtotal:
        raise CouponError(
            "min_subtotal", f"حداقل مبلغ سفارش برای این کد {coupon.min_subtotal:,} تومان است"
        )
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise CouponError("exhausted", "ظرفیت استفاده از این کد تخفیف تکمیل شده است")
    if prior_uses >= coupon.max_uses_per_user:
        raise CouponError("per_user_limit", "شما قبلاً از این کد تخفیف استفاده کرده‌اید")

    return compute_discount(coupon, subtotal)


async def count_user_redemptions(session: AsyncSession, coupon_id: UUID, user_id: UUID) -> int:
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM public.coupon_redemptions "
            "WHERE coupon_id = :cid AND user_id = :uid"
        ),
        {"cid": str(coupon_id), "uid": str(user_id)},
    )
    return int(row.scalar_one())


async def record_redemption(
    session: AsyncSession, coupon: Coupon, order_id: UUID, user_id: UUID, amount: int
) -> None:
    await session.execute(
        text(
            "INSERT INTO public.coupon_redemptions (coupon_id, order_id, user_id, amount) "
            "VALUES (:cid, :oid, :uid, :amount)"
        ),
        {"cid": str(coupon.id), "oid": str(order_id), "uid": str(user_id), "amount": int(amount)},
    )
    await session.execute(
        text("UPDATE public.coupons SET used_count = used_count + 1 WHERE id = :cid"),
        {"cid": str(coupon.id)},
    )


def decimal_to_int(value: Decimal | int | None) -> int:
    return int(value) if value is not None else 0
