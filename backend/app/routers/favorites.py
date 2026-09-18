"""Favorites endpoints (scoped to the token's user)."""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import CurrentUser, DbSession
from app.schemas import FavoriteToggleOut

log = logging.getLogger(__name__)
router = APIRouter(tags=["favorites"])


@router.get("/favorites", response_model=list[str])
async def list_favorites(user: CurrentUser, session: DbSession) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT product_id FROM public.favorites WHERE user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": str(user.id)},
    )
    return [r[0] for r in rows.all()]


@router.post("/favorites/{product_id}", response_model=FavoriteToggleOut)
async def toggle_favorite(
    product_id: str, user: CurrentUser, session: DbSession
) -> FavoriteToggleOut:
    existing = (
        await session.execute(
            text(
                "SELECT id FROM public.favorites WHERE user_id = :uid AND product_id = :pid"
            ),
            {"uid": str(user.id), "pid": product_id},
        )
    ).first()

    if existing is not None:
        await session.execute(
            text("DELETE FROM public.favorites WHERE id = :fid"),
            {"fid": existing[0]},
        )
        await session.commit()
        return FavoriteToggleOut(product_id=product_id, is_favorite=False)

    # product must exist (FK would fail otherwise)
    product = (
        await session.execute(
            text("SELECT 1 FROM public.products WHERE id = :pid"), {"pid": product_id}
        )
    ).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")

    await session.execute(
        text(
            "INSERT INTO public.favorites (user_id, product_id) VALUES (:uid, :pid) "
            "ON CONFLICT (user_id, product_id) DO NOTHING"
        ),
        {"uid": str(user.id), "pid": product_id},
    )
    await session.commit()
    return FavoriteToggleOut(product_id=product_id, is_favorite=True)
