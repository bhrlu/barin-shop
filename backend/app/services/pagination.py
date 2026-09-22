"""Pagination helpers shared by list endpoints (F2.5).

Envelope shape: `{items, total, page, page_size, pages}`. List endpoints keep
their bare-list responses for callers that omit `page` (backward compatibility
with existing clients), and switch to the envelope as soon as `page` is
provided.
"""

from typing import Any

from fastapi import Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def page_params(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
) -> tuple[int, int]:
    """Dependency: 0/0 means "no pagination" (legacy bare list)."""
    return page, page_size


def clamp_page_size(
    page: int, page_size: int, default_size: int, max_size: int = 100
) -> tuple[int, int]:
    """Resolve effective (page, size) for callers using the envelope."""
    if page <= 0:
        return 0, 0
    if page_size <= 0:
        page_size = default_size
    return page, min(page_size, max_size)


def envelope(items: list[Any], total: int, page: int, page_size: int) -> dict:
    pages = (total + page_size - 1) // page_size if page_size else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(pages, 1),
    }


def apply_limit_offset(sql: str, page: int, page_size: int) -> str:
    """Append LIMIT/OFFSET when paginating; pass through otherwise."""
    if page <= 0:
        return sql
    return sql + f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"


async def count_rows(session: AsyncSession, base_sql: str, params: dict) -> int:
    """Run `SELECT COUNT(*) FROM (<base_sql>) AS q` and return the total.

    base_sql must NOT include ORDER BY (wrap it as a subquery, which Postgres
    requires anyway for COUNT over an ordered select).
    """
    wrapped = f"SELECT COUNT(*) FROM ({base_sql}) AS q"
    row = await session.execute(text(wrapped), params)
    return int(row.scalar() or 0)
