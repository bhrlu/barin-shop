"""Role resolution shared by auth dependencies and routers."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_role(session: AsyncSession, user_id: UUID) -> str:
    """Highest-privilege role wins; default to customer."""
    row = await session.execute(
        text("SELECT role FROM public.user_roles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    roles = {r[0] for r in row.all()}
    if "admin" in roles:
        return "admin"
    return "customer"
