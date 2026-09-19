"""Search endpoints.

GET    /search          — full search (records history for signed-in users)
GET    /search/suggest  — autocomplete suggestions (products, categories, tags, recent)
GET    /search/history  — signed-in customer's recent searches
DELETE /search/history  — clear the customer's history
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.auth import CurrentUser, DbSession, OptionalUser
from app.schemas import (
    SearchHistoryOut,
    SearchHit,
    SearchOut,
    SearchSuggestion,
)
from app.services.search import search_products

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


async def _record_history(session, user_id, query: str) -> None:
    """Keep the latest entry per (user, query) so history doesn't fill with dupes."""
    await session.execute(
        text(
            "INSERT INTO public.search_history (user_id, query) "
            "VALUES (:uid, :q) ON CONFLICT DO NOTHING"
        ),
        {"uid": str(user_id), "q": query},
    )
    # collapse duplicates, keep the most recent occurrence
    await session.execute(
        text(
            "DELETE FROM public.search_history a USING public.search_history b "
            "WHERE a.user_id = b.user_id AND a.query = b.query "
            "  AND a.created_at < b.created_at"
        )
    )
    await session.commit()


@router.get("", response_model=SearchOut)
async def search(
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=100),
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: OptionalUser = None,
) -> SearchOut:
    result = await search_products(
        session, q, category=category, limit=limit, offset=offset
    )
    if user is not None and offset == 0:
        await _record_history(session, user.id, result["query"])
    return SearchOut(
        query=result["query"],
        total=result["total"],
        hits=[SearchHit(**h) for h in result["hits"]],
    )


@router.get("/suggest", response_model=list[SearchSuggestion])
async def suggest(
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=8, ge=1, le=20),
    user: OptionalUser = None,
) -> list[SearchSuggestion]:
    """Autocomplete: recent queries, matching categories/tags, then products."""
    needle = q.strip()
    if not needle:
        return []
    pattern = f"{needle}%"
    contains = f"%{needle}%"
    out: list[SearchSuggestion] = []

    # 1) the user's own past queries that start with the prefix
    if user is not None:
        history = (
            await session.execute(
                text(
                    "SELECT DISTINCT query FROM public.search_history "
                    "WHERE user_id = :uid AND query ILIKE :pat "
                    "ORDER BY query LIMIT 3"
                ),
                {"uid": str(user.id), "pat": pattern},
            )
        ).all()
        out.extend(
            SearchSuggestion(id=None, label=row[0], kind="query") for row in history
        )

    # 2) categories that match
    categories = (
        await session.execute(
            text(
                "SELECT DISTINCT category FROM public.products "
                "WHERE active AND category ILIKE :pat ORDER BY category LIMIT 3"
            ),
            {"pat": pattern},
        )
    ).all()
    out.extend(
        SearchSuggestion(id=None, label=row[0], kind="category") for row in categories
    )

    # 3) matching tags
    tags = (
        await session.execute(
            text(
                "SELECT DISTINCT t FROM public.products p, unnest(p.tags) AS t "
                "WHERE p.active AND t ILIKE :pat ORDER BY t LIMIT 3"
            ),
            {"pat": pattern},
        )
    ).all()
    out.extend(SearchSuggestion(id=None, label=row[0], kind="tag") for row in tags)

    # 4) products (fill the remaining slots)
    remaining = max(0, limit - len(out))
    if remaining:
        products = (
            await session.execute(
                text(
                    "SELECT id, name, images FROM public.products "
                    "WHERE active AND (name ILIKE :contains OR category ILIKE :contains) "
                    "ORDER BY (name ILIKE :pat) DESC, is_new DESC, created_at DESC "
                    "LIMIT :limit"
                ),
                {"pat": pattern, "contains": contains, "limit": remaining},
            )
        ).mappings().all()
        out.extend(
            SearchSuggestion(
                id=r["id"],
                label=r["name"],
                kind="product",
                image=(r["images"] or [None])[0],
            )
            for r in products
        )

    return out[:limit]


@router.get("/history", response_model=list[SearchHistoryOut])
async def history(
    user: CurrentUser, session: DbSession, limit: int = Query(default=10, ge=1, le=50)
) -> list[SearchHistoryOut]:
    rows = (
        await session.execute(
            text(
                "SELECT id, query, created_at FROM public.search_history "
                "WHERE user_id = :uid ORDER BY created_at DESC LIMIT :limit"
            ),
            {"uid": str(user.id), "limit": limit},
        )
    ).mappings().all()
    return [
        SearchHistoryOut(
            id=r["id"],
            query=r["query"],
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
        )
        for r in rows
    ]


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(user: CurrentUser, session: DbSession) -> None:
    await session.execute(
        text("DELETE FROM public.search_history WHERE user_id = :uid"),
        {"uid": str(user.id)},
    )
    await session.commit()


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: UUID, user: CurrentUser, session: DbSession
) -> None:
    result = await session.execute(
        text("DELETE FROM public.search_history WHERE id = :eid AND user_id = :uid"),
        {"eid": str(entry_id), "uid": str(user.id)},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "موردی پیدا نشد")
