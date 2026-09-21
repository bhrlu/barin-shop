"""Contact-form messages.

The contact page used to be display-only (a toast). `POST /contact` now stores
the message so support can actually answer it; `GET /admin/contact-messages`
is the inbox the admin panel reads (F2.1b) and `PATCH
/admin/contact-messages/{id}` marks one answered (`status = 'answered'`).

`POST /contact` is public: a guest must be able to ask about a size or an order
without an account. `user_id` is therefore left NULL and the sender's own
`contact` field carries the way to reply.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.auth import AdminUser, DbSession
from app.schemas import ContactMessageIn, ContactMessageOut, ContactMessageStatusIn

log = logging.getLogger(__name__)
router = APIRouter(tags=["contact"])


def _row_to_out(row) -> ContactMessageOut:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return ContactMessageOut(**d)


@router.post(
    "/contact", response_model=ContactMessageOut, status_code=status.HTTP_201_CREATED
)
async def create_message(body: ContactMessageIn, session: DbSession) -> ContactMessageOut:
    """Store a contact-form message (public — no account required)."""
    row = (
        await session.execute(
            text(
                "INSERT INTO public.contact_messages (name, contact, message) "
                "VALUES (:name, :contact, :message) "
                "RETURNING id, user_id, name, contact, message, status, created_at"
            ),
            {"name": body.name, "contact": body.contact, "message": body.message},
        )
    ).mappings().first()
    await session.commit()
    log.info("contact message stored from %s", body.contact)
    return _row_to_out(row)


@router.get("/admin/contact-messages", response_model=list[ContactMessageOut])
async def list_messages(
    user: AdminUser,
    session: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ContactMessageOut]:
    """Newest first; `?status=new` narrows to unanswered ones."""
    sql = (
        "SELECT id, user_id, name, contact, message, status, created_at "
        "FROM public.contact_messages"
    )
    params: dict = {"limit": limit}
    if status_filter:
        sql += " WHERE status = :status"
        params["status"] = status_filter
    sql += " ORDER BY created_at DESC LIMIT :limit"
    rows = (await session.execute(text(sql), params)).mappings().all()
    return [_row_to_out(r) for r in rows]


@router.delete(
    "/admin/contact-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_message(message_id: UUID, user: AdminUser, session: DbSession) -> None:
    """Remove a message (spam, or one that has been answered elsewhere)."""
    result = await session.execute(
        text("DELETE FROM public.contact_messages WHERE id = :mid"),
        {"mid": str(message_id)},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیام پیدا نشد")


@router.patch("/admin/contact-messages/{message_id}", response_model=ContactMessageOut)
async def mark_message(
    message_id: UUID, body: ContactMessageStatusIn, user: AdminUser, session: DbSession
) -> ContactMessageOut:
    """Mark a message answered (`status = 'answered'`) or reopen it (`'new'`).

    Answering happens over email/phone — the flag just keeps the inbox honest.
    """
    row = (
        await session.execute(
            text(
                "UPDATE public.contact_messages SET status = :status "
                "WHERE id = CAST(:mid AS uuid) "
                "RETURNING id, user_id, name, contact, message, status, created_at"
            ),
            {"mid": str(message_id), "status": body.status},
        )
    ).mappings().first()
    if row is None:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیام پیدا نشد")
    await session.commit()
    return _row_to_out(row)
