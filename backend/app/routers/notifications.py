"""In-app notifications + the admin channel switches (B2.1, decision D2).

- GET   /notifications                  — the caller's notifications, newest first
                                          (always the `Page<T>` envelope; `unread=true`)
- GET   /notifications/unread-count     — `{unread}` for the header bell
- PATCH /notifications/{id}/read        — mark one of the caller's own as read
- POST  /notifications/read-all         — mark all of the caller's own as read
- GET   /admin/settings/notifications   — SMS/email switches + provider state
- PATCH /admin/settings/notifications   — flip the switches (audited)

Notifications are created only by `app/services/notifications.py` at the
business lifecycle points; nothing here writes one. Every inbox query is scoped
to the caller in SQL, so another user's id answers 404 like a missing one.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import text

from app.auth import CurrentUser, DbSession, StaffSettings
from app.services import notifications
from app.services.audit import record_audit
from app.services.pagination import count_rows, envelope

router = APIRouter(tags=["notifications"])

_SELECT = (
    "SELECT id, type, title, message, data, read_at, created_at "
    "FROM public.notifications WHERE user_id = CAST(:uid AS uuid)"
)


def _item(row) -> dict:
    return {
        "id": str(row["id"]),
        "type": row["type"],
        "title": row["title"],
        "message": row["message"],
        "data": row["data"] or {},
        "read_at": row["read_at"].isoformat() if row["read_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/notifications")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread: bool = Query(default=False),
) -> dict:
    """The caller's notifications, newest first. A new endpoint has no legacy
    bare-list callers, so it always answers with the pagination envelope."""
    base_sql = _SELECT + (" AND read_at IS NULL" if unread else "")
    params = {"uid": str(user.id)}
    total = await count_rows(session, base_sql, params)
    rows = (
        await session.execute(
            text(
                base_sql + " ORDER BY created_at DESC, id DESC "
                f"LIMIT {page_size} OFFSET {(page - 1) * page_size}"
            ),
            params,
        )
    ).mappings().all()
    return envelope([_item(r) for r in rows], total, page, page_size)


@router.get("/notifications/unread-count")
async def unread_count(user: CurrentUser, session: DbSession) -> dict:
    count = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM public.notifications "
                "WHERE user_id = CAST(:uid AS uuid) AND read_at IS NULL"
            ),
            {"uid": str(user.id)},
        )
    ).scalar_one()
    return {"unread": int(count)}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(notification_id: UUID, user: CurrentUser, session: DbSession) -> dict:
    """Idempotent: an already-read notification keeps its first `read_at`."""
    row = (
        await session.execute(
            text(
                "UPDATE public.notifications SET read_at = COALESCE(read_at, now()) "
                "WHERE id = CAST(:nid AS uuid) AND user_id = CAST(:uid AS uuid) "
                "RETURNING id, type, title, message, data, read_at, created_at"
            ),
            {"nid": str(notification_id), "uid": str(user.id)},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلان پیدا نشد")
    return _item(row)


@router.post("/notifications/read-all")
async def mark_all_read(user: CurrentUser, session: DbSession) -> dict:
    result = await session.execute(
        text(
            "UPDATE public.notifications SET read_at = now() "
            "WHERE user_id = CAST(:uid AS uuid) AND read_at IS NULL"
        ),
        {"uid": str(user.id)},
    )
    return {"updated": result.rowcount}


# --- admin: external channel switches ---------------------------------------------


class NotificationSettingsIn(BaseModel):
    """Partial update; at least one switch. The in-app inbox has no switch."""

    model_config = ConfigDict(extra="forbid")

    sms_enabled: StrictBool | None = None
    email_enabled: StrictBool | None = None


@router.get("/admin/settings/notifications")
async def get_notification_settings(user: StaffSettings, session: DbSession) -> dict:
    return notifications.channel_state(await notifications.load_switches(session))


@router.patch("/admin/settings/notifications")
async def update_notification_settings(
    body: NotificationSettingsIn, user: StaffSettings, session: DbSession
) -> dict:
    if body.sms_enabled is None and body.email_enabled is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")
    before = await notifications.load_switches(session)
    await notifications.save_switches(
        session, sms=body.sms_enabled, email=body.email_enabled, admin_id=user.id
    )
    after = await notifications.load_switches(session)
    await record_audit(
        session,
        admin_id=user.id,
        action="update_notification_settings",
        entity_type="settings",
        entity_id="notifications",
        old_values={"sms_enabled": before["sms"], "email_enabled": before["email"]},
        new_values={"sms_enabled": after["sms"], "email_enabled": after["email"]},
    )
    await session.commit()
    return notifications.channel_state(after)
