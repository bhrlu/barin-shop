"""Admin audit log (B5.1, spec [BE-04]).

One row per privileged mutation: who did what to which entity, with the old/new
values where the router has them. Uses the request's own session so the entry
commits atomically with the mutation it describes — an admin action without its
audit trail, or vice versa, must not happen.
"""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# documented action vocabulary; new privileged mutations should reuse or extend it
ACTIONS = {
    "update_order_status",
    "update_order_payment_status",
    "update_order_tracking_code",
    "cancel_order",
    "resolve_refund",
    "create_product",
    "update_product",
    "delete_product",
    "create_variant",
    "update_variant",
    "delete_variant",
    "create_coupon",
    "update_coupon",
    "moderate_review",
    "delete_review",
    "update_user_roles",
}

_ENTITY_TYPES = {"order", "product", "variant", "coupon", "review", "user"}


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

    Never raises into the request path: a failed audit write is logged, not
    propagated — the mutation itself has already succeeded or failed on its own
    terms. (A stricter all-or-nothing coupling would let a broken audit insert
    roll back a legitimate order-status change.)
    """
    if action not in ACTIONS:
        log.warning("audit: unknown action %r", action)
    if entity_type not in _ENTITY_TYPES:
        log.warning("audit: unknown entity_type %r", entity_type)

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
    except Exception:  # noqa: BLE001
        await session.rollback()
        log.exception("audit: failed to record %s on %s", action, entity_id)
