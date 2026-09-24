"""Admin audit log (B5.1, spec [BE-04]).

One row per privileged mutation: who did what to which entity, with the old/new
values where the router has them. Uses the request's own session so the entry
commits atomically with the mutation it describes — an admin action without its
audit trail, or vice versa, must not happen. Every caller records the entry
before it commits, so a failed insert fails the request (B5.1d).

The client IP (B5.1a) is captured per request by the middleware in
`app.main`, which sets `client_ip_ctx` on every inbound call; `record_audit`
reads it when the caller does not pass an explicit `ip_address`. The address
comes from `app.services.client_ip.resolve_client_ip`: `X-Forwarded-For` is
believed only from a configured trusted proxy, so a caller cannot forge it.
"""

import json
import logging
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# set per request by the middleware in app.main (B5.1a)
client_ip_ctx: ContextVar[str | None] = ContextVar("client_ip", default=None)

# documented action vocabulary; new privileged mutations should reuse or extend it
ACTIONS = {
    "update_order_status",
    "update_order_payment_status",
    "update_order_tracking_code",
    "cancel_order",
    "resolve_refund",
    "create_product",
    "import_products",
    "update_product",
    "delete_product",
    "create_variant",
    "update_variant",
    "delete_variant",
    "create_coupon",
    "update_coupon",
    "delete_coupon",
    "moderate_review",
    "delete_review",
    "update_user_roles",
    "update_notification_settings",
}

_ENTITY_TYPES = {"order", "product", "variant", "coupon", "review", "user", "settings"}


async def record_audit(
    session: AsyncSession,
    *,
    admin_id,
    action: str,
    entity_type: str,
    entity_id: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert one audit_logs row on the caller's session (no commit here).

    A failed insert is logged and **re-raised** (B5.1d): the request answers 500
    and `get_session` rolls the whole transaction back, so the audited mutation
    and its entry land together or not at all. The previous behaviour — roll
    back and carry on — silently discarded the mutation while the router still
    committed an empty transaction and answered 200.
    """
    if action not in ACTIONS:
        log.warning("audit: unknown action %r", action)
    if entity_type not in _ENTITY_TYPES:
        log.warning("audit: unknown entity_type %r", entity_type)
    if ip_address is None:
        ip_address = client_ip_ctx.get()

    try:
        await session.execute(
            text(
                "INSERT INTO public.audit_logs "
                "(admin_id, action, entity_type, entity_id, old_values, new_values, ip_address) "
                "VALUES (CAST(:admin AS uuid), :action, :etype, :eid, "
                "CAST(:old AS jsonb), CAST(:new AS jsonb), :ip)"
            ),
            {
                "admin": str(admin_id),
                "action": action,
                "etype": entity_type,
                "eid": str(entity_id),
                "old": json.dumps(old_values or {}, ensure_ascii=False, default=str),
                "new": json.dumps(new_values or {}, ensure_ascii=False, default=str),
                "ip": ip_address,
            },
        )
    except Exception:
        log.exception("audit: failed to record %s on %s — failing the request", action, entity_id)
        raise
