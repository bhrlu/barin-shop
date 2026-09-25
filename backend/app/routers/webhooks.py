"""Outbound order webhooks: admin state + deliveries (B2.5a, decision D11).

- GET   /admin/settings/webhooks          — read-only integration state (env-driven)
- GET   /admin/webhooks/deliveries        — the outbox, newest first (`Page<T>`)
- POST  /admin/webhooks/deliveries/{id}/redeliver — re-queue one `failed` row

There is no PATCH on the settings: the endpoint URL and the HMAC secret are
env-only by D11, so nothing here can change them. Every mutation is audited;
the deliveries list is scoped exactly like the audit-log viewer, so the guard
family (`StaffSettings`) is the same one that guards the notification switches.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.auth import DbSession, StaffSettings
from app.services import webhooks
from app.services.audit import record_audit
from app.services.pagination import count_rows, envelope

router = APIRouter(tags=["webhooks"])


@router.get("/admin/settings/webhooks")
async def get_webhook_settings(user: StaffSettings) -> dict:
    """Read-only integration state (D11: the URL and secret are env-only)."""
    return webhooks.state()


_DELIVERY_SELECT = (
    "SELECT id, event, order_id, status, attempts, last_error, response_status, "
    "created_at, updated_at FROM public.webhook_deliveries"
)


def _item(row) -> dict:
    return {
        "id": str(row["id"]),
        "event": row["event"],
        "order_id": str(row["order_id"]),
        "status": row["status"],
        "attempts": int(row["attempts"]),
        "last_error": row["last_error"],
        "response_status": row["response_status"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@router.get("/admin/webhooks/deliveries")
async def list_webhook_deliveries(
    user: StaffSettings,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str = Query(default="", alias="status"),
) -> dict:
    """The outbox, newest first, with an optional status filter."""
    base_sql = _DELIVERY_SELECT
    params: dict = {}
    if status_filter:
        if status_filter not in ("pending", "sent", "failed", "skipped"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت نامعتبر است")
        base_sql += " WHERE status = :status"
        params["status"] = status_filter
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


@router.post("/admin/webhooks/deliveries/{delivery_id}/redeliver")
async def redeliver_webhook(
    delivery_id: UUID, user: StaffSettings, session: DbSession
) -> dict:
    """Re-queue a `failed` delivery (audited). Sent right after this commit."""
    row = await webhooks.redeliver(session, delivery_id)
    if not row:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "فقط ارسال ناموفق قابل ارسال مجدد است",
        )
    await record_audit(
        session,
        admin_id=user.id,
        action="redeliver_webhook",
        entity_type="webhook_delivery",
        entity_id=str(delivery_id),
        new_values={"event": row["event"], "order_id": row["order_id"]},
    )
    await session.commit()
    return {**row, "status": "pending"}
