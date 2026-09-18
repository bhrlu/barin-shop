"""Address book endpoints for the signed-in customer (scoped to the token)."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import CurrentUser, DbSession
from app.schemas import AddressIn, AddressOut

log = logging.getLogger(__name__)
router = APIRouter(tags=["addresses"])

_SELECT = (
    "SELECT id, user_id, title, receiver, phone, province, city, postal_code, "
    "line, is_default, created_at FROM public.addresses WHERE user_id = :uid"
)


@router.get("/addresses", response_model=list[AddressOut])
async def list_addresses(user: CurrentUser, session: DbSession) -> list[AddressOut]:
    rows = (
        await session.execute(
            text(_SELECT + " ORDER BY created_at DESC"), {"uid": str(user.id)}
        )
    ).mappings().all()
    return [AddressOut(**dict(r)) for r in rows]


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(body: AddressIn, user: CurrentUser, session: DbSession) -> AddressOut:
    row = (
        await session.execute(
            text(
                "INSERT INTO public.addresses "
                "(user_id, title, receiver, phone, province, city, postal_code, line, is_default) "
                "VALUES (:uid, :title, :receiver, :phone, :province, :city, :postal, :line, :isd) "
                "RETURNING id, user_id, title, receiver, phone, province, city, postal_code, "
                "line, is_default, created_at"
            ),
            {
                "uid": str(user.id),
                "title": body.title,
                "receiver": body.receiver,
                "phone": body.phone,
                "province": body.province,
                "city": body.city,
                "postal": body.postal_code,
                "line": body.line,
                "isd": body.is_default,
            },
        )
    ).mappings().first()
    await session.commit()
    return AddressOut(**dict(row))


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: UUID, user: CurrentUser, session: DbSession) -> None:
    result = await session.execute(
        text("DELETE FROM public.addresses WHERE id = :aid AND user_id = :uid"),
        {"aid": str(address_id), "uid": str(user.id)},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آدرس پیدا نشد")
