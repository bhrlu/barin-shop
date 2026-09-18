"""Search endpoint."""

from fastapi import APIRouter, Query

from app.auth import DbSession
from app.schemas import SearchHit, SearchOut
from app.services.search import search_products

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchOut)
async def search(
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=100),
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> SearchOut:
    result = await search_products(
        session, q, category=category, limit=limit, offset=offset
    )
    return SearchOut(
        query=result["query"],
        total=result["total"],
        hits=[SearchHit(**h) for h in result["hits"]],
    )
