"""Address book endpoints for the signed-in customer (scoped to the token).

A customer has **at most one default address**: creating the first one makes it
default, creating another with `is_default` moves the flag, deleting the default
promotes the most recent remaining address, and the default is what the checkout
page pre-fills.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import CurrentUser, DbSession
from app.schemas import AddressIn, AddressOut, AddressUpdateIn

log = logging.getLogger(__name__)
router = APIRouter(tags=["addresses"])

_SELECT = (
    "SELECT id, user_id, title, receiver, phone, province, city, postal_code, "
    "line, is_default, created_at FROM public.addresses WHERE user_id = :uid"
)

# Newest default first so the checkout pre-fill has a deterministic order.
_ORDER = " ORDER BY is_default DESC, created_at DESC"


def _row_to_out(row) -> AddressOut:
    """AddressOut.created_at is typed `str`, so the DB's datetime must be
    isoformatted — Pydantic v2 rejects a raw datetime for a str field (500)."""
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return AddressOut(**d)


async def _clear_default(session, user_id: UUID, keep: str | None = None) -> None:
    """Make `keep` the only default for this customer (all others cleared)."""
    await session.execute(
        text(
            "UPDATE public.addresses SET is_default = (id = CAST(:keep AS uuid)) "
            "WHERE user_id = :uid"
        ),
        {"uid": str(user_id), "keep": keep},
    )


@router.get("/addresses", response_model=list[AddressOut])
async def list_addresses(user: CurrentUser, session: DbSession) -> list[AddressOut]:
    rows = (
        await session.execute(text(_SELECT + _ORDER), {"uid": str(user.id)})
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(body: AddressIn, user: CurrentUser, session: DbSession) -> AddressOut:
    """Add an address. An explicit `is_default` (or being the first address) makes
    it the customer's default and clears the flag everywhere else."""
    is_first = (
        await session.execute(
            text("SELECT COUNT(*) FROM public.addresses WHERE user_id = :uid"),
            {"uid": str(user.id)},
        )
    ).scalar_one() == 0
    make_default = bool(body.is_default) or is_first

    row = (
        await session.execute(
            text(
                "INSERT INTO public.addresses "
                "(user_id, title, receiver, phone, province, city, postal_code, line, is_default) "
                "VALUES (:uid, :title, :receiver, :phone, :province, :city, :postal, :line, false) "
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
            },
        )
    ).mappings().first()

    if make_default:
        await _clear_default(session, user.id, keep=str(row["id"]))
        row = dict(row)
        row["is_default"] = True

    await session.commit()
    return _row_to_out(row)


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: UUID, body: AddressUpdateIn, user: CurrentUser, session: DbSession
) -> AddressOut:
    """Edit an address and/or make it the default."""
    owned = (
        await session.execute(
            text("SELECT id FROM public.addresses WHERE id = :aid AND user_id = :uid"),
            {"aid": str(address_id), "uid": str(user.id)},
        )
    ).first()
    if owned is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آدرس پیدا نشد")

    sets: list[str] = []
    params: dict = {"aid": str(address_id), "uid": str(user.id)}
    for field in ("title", "receiver", "phone", "province", "city", "postal_code", "line"):
        value = getattr(body, field)
        if value is not None:
            sets.append(f"{field} = :{field}")
            params[field] = value

    if body.is_default:
        # the flag is applied through the single-default helper below
        pass
    elif body.is_default is False:
        sets.append("is_default = false")

    if sets:
        await session.execute(
            text(
                f"UPDATE public.addresses SET {', '.join(sets)} "
                "WHERE id = :aid AND user_id = :uid"
            ),
            params,
        )
    if body.is_default:
        await _clear_default(session, user.id, keep=str(address_id))

    await session.commit()

    row = (
        await session.execute(
            text(_SELECT + " AND id = :aid"), {"uid": str(user.id), "aid": str(address_id)}
        )
    ).mappings().first()
    if row is None:  # deleted concurrently
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آدرس پیدا نشد")
    return _row_to_out(row)


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: UUID, user: CurrentUser, session: DbSession) -> None:
    """Delete an address; if it was the default, the most recent remaining one
    takes over so a customer with saved addresses always has a default."""
    result = await session.execute(
        text(
            "DELETE FROM public.addresses WHERE id = :aid AND user_id = :uid "
            "RETURNING is_default"
        ),
        {"aid": str(address_id), "uid": str(user.id)},
    )
    deleted = result.mappings().first()
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آدرس پیدا نشد")

    if deleted["is_default"]:
        successor = (
            await session.execute(
                text(
                    "SELECT id FROM public.addresses WHERE user_id = :uid "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"uid": str(user.id)},
            )
        ).first()
        if successor is not None:
            await _clear_default(session, user.id, keep=str(successor[0]))

    await session.commit()
