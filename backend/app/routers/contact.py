"""Contact-form messages.

The contact page used to be display-only (a toast). `POST /contact` now stores
the message so support can actually answer it; `GET /admin/contact-messages`
is the inbox the admin panel reads (F2.1b) and `PATCH
/admin/contact-messages/{id}` marks one answered (`status = 'answered'`).

`POST /contact` is public: a guest must be able to ask about a size or an order
without an account. `user_id` is therefore left NULL and the sender's own
`contact` field carries the way to reply. Because it is public it is guarded
(B3.11): a per-IP throttle and a honeypot field, see `services.contact_guard`.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.auth import DbSession, StaffContactInbox
from app.schemas import ContactMessageIn, ContactMessageOut, ContactMessageStatusIn
from app.services import contact_guard
from app.services.audit import client_ip_ctx
from app.services.pagination import clamp_page_size, count_rows, envelope

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
    # B3.11 guard: 429 once the caller's IP has used its attempts for the window,
    # 400 when the honeypot field is filled. Both answers are deliberately
    # generic, and this is a comment, not the docstring, because FastAPI
    # publishes endpoint docstrings in the public OpenAPI schema.
    outcome = await contact_guard.record_attempt(
        session, ip=client_ip_ctx.get(), honeypot=bool((body.website or "").strip())
    )
    if outcome != contact_guard.ACCEPTED:
        # rejected attempts count toward the window (D1) — keep the row even
        # though the request fails
        await session.commit()
        log.info("contact attempt rejected (%s)", outcome)
        if outcome == contact_guard.THROTTLED:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "تعداد پیام‌های ارسالی زیاد است؛ لطفاً کمی بعد دوباره تلاش کنید.",
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "ارسال پیام ممکن نشد؛ لطفاً دوباره تلاش کنید."
        )
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


@router.get("/admin/contact-messages")
async def list_messages(
    user: StaffContactInbox,
    session: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
) -> list[ContactMessageOut] | dict:
    """Newest first; `?status=new` narrows to unanswered ones.
    Envelope when `page` is given."""
    base_sql = (
        "SELECT id, user_id, name, contact, message, status, created_at "
        "FROM public.contact_messages"
    )
    params: dict = {}
    if status_filter:
        base_sql += " WHERE status = :status"
        params["status"] = status_filter
    page, page_size = clamp_page_size(page, page_size, default_size=20)
    sql = base_sql + " ORDER BY created_at DESC"
    total = 0
    if page > 0:
        total = await count_rows(session, base_sql, params)
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    else:
        sql += " LIMIT :limit"
        params["limit"] = limit
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [_row_to_out(r) for r in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.delete(
    "/admin/contact-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_message(message_id: UUID, user: StaffContactInbox, session: DbSession) -> None:
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
    message_id: UUID, body: ContactMessageStatusIn, user: StaffContactInbox, session: DbSession
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
