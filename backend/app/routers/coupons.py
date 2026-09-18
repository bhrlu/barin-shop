"""Coupon endpoints.

Public (authenticated): validate a code against a subtotal — used by the cart UI.
Admin: create / list / update coupons (SÂNDÉ codes like SANDE10 can now be real rows).
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import AdminUser, CurrentUser, DbSession
from app.models import Coupon
from app.schemas import CouponCreate, CouponOut, CouponUpdate, CouponValidateRequest
from app.services.coupons import (
    CouponError,
    compute_discount,
    count_user_redemptions,
    generate_code,
    validate_coupon,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/coupons", tags=["coupons"])


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


@router.post("/validate", response_model=CouponOut)
async def validate(
    body: CouponValidateRequest,
    user: CurrentUser,
    session: DbSession,
) -> CouponOut:
    code = body.code.strip().upper()
    row = (
        await session.execute(
            text("SELECT * FROM public.coupons WHERE code = :code"), {"code": code}
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کد تخفیف معتبر نیست")

    coupon = Coupon(**row)
    prior = await count_user_redemptions(session, coupon.id, user.id)
    try:
        discount = validate_coupon(coupon, body.subtotal, user.id, prior)
    except CouponError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message_fa) from exc

    return CouponOut(
        code=coupon.code,
        discount=discount,
        percent_off=coupon.percent_off,
        amount_off=coupon.amount_off,
        min_subtotal=coupon.min_subtotal,
        expires_at=_iso(coupon.expires_at),
    )


@router.post("", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(body: CouponCreate, admin: AdminUser, session: DbSession) -> CouponOut:
    code = body.code.strip().upper()
    exists = (
        await session.execute(
            text("SELECT 1 FROM public.coupons WHERE code = :code"), {"code": code}
        )
    ).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کد قبلاً ثبت شده است")

    expires = None
    if body.expires_at:
        try:
            expires = datetime.fromisoformat(body.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "تاریخ انقضا نامعتبر است"
            ) from exc

    row = (
        await session.execute(
            text(
                "INSERT INTO public.coupons "
                "(code, percent_off, amount_off, min_subtotal, max_uses, "
                " max_uses_per_user, expires_at) "
                "VALUES (:code, :percent, :amount, :min_sub, :max_uses, :max_user, :expires) "
                "RETURNING *"
            ),
            {
                "code": code,
                "percent": body.percent_off,
                "amount": body.amount_off,
                "min_sub": body.min_subtotal,
                "max_uses": body.max_uses,
                "max_user": body.max_uses_per_user,
                "expires": expires,
            },
        )
    ).mappings().first()

    return CouponOut(
        code=row["code"],
        discount=0,
        percent_off=row["percent_off"],
        amount_off=row["amount_off"],
        min_subtotal=int(row["min_subtotal"]),
        expires_at=_iso(row["expires_at"]),
    )


@router.get("")
async def list_coupons(admin: AdminUser, session: DbSession) -> dict:
    rows = (
        await session.execute(text("SELECT * FROM public.coupons ORDER BY created_at DESC"))
    ).mappings().all()
    return {
        "coupons": [
            {
                "id": str(r["id"]),
                "code": r["code"],
                "percent_off": r["percent_off"],
                "amount_off": r["amount_off"],
                "min_subtotal": int(r["min_subtotal"]),
                "max_uses": r["max_uses"],
                "max_uses_per_user": int(r["max_uses_per_user"]),
                "used_count": int(r["used_count"]),
                "expires_at": _iso(r["expires_at"]),
                "active": bool(r["active"]),
            }
            for r in rows
        ]
    }


@router.patch("/{coupon_id}")
async def update_coupon(
    coupon_id: UUID, body: CouponUpdate, admin: AdminUser, session: DbSession
) -> dict:
    row = (
        await session.execute(
            text("SELECT * FROM public.coupons WHERE id = :cid FOR UPDATE"),
            {"cid": str(coupon_id)},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کد تخفیف پیدا نشد")

    fields: dict = {}
    if body.active is not None:
        fields["active"] = body.active
    if body.percent_off is not None:
        fields["percent_off"] = body.percent_off
    if body.amount_off is not None:
        fields["amount_off"] = body.amount_off
    if body.min_subtotal is not None:
        fields["min_subtotal"] = body.min_subtotal
    if body.max_uses is not None:
        fields["max_uses"] = body.max_uses
    if body.max_uses_per_user is not None:
        fields["max_uses_per_user"] = body.max_uses_per_user
    if body.expires_at is not None:
        if body.expires_at == "":
            fields["expires_at"] = None
        else:
            try:
                fields["expires_at"] = datetime.fromisoformat(
                    body.expires_at.replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "تاریخ انقضا نامعتبر است"
                ) from exc

    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["cid"] = str(coupon_id)
        await session.execute(
            text(f"UPDATE public.coupons SET {sets} WHERE id = :cid"), fields
        )

    return {"ok": True}


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate(admin: AdminUser, session: DbSession, prefix: str = "SANDE") -> dict:
    """Convenience: mint a fresh unused code (admin picks its rules separately)."""
    code = generate_code(prefix.upper())
    return {"code": code}


# re-exported so tests can use compute_discount without importing services
__all__ = ["router", "compute_discount"]
