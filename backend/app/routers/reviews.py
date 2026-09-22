"""Product reviews & star ratings.

Public:
  GET    /products/{id}/reviews        — published reviews + rating summary
Admin:
  GET    /admin/reviews                — all reviews (optionally by status)
Signed-in:
  POST   /products/{id}/reviews        — create or replace your review
  DELETE /reviews/{id}                 — delete your own review
Admin:
  PATCH  /reviews/{id}                 — moderate status and/or post a seller reply
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text

from app.auth import CurrentUser, DbSession, StaffReviews
from app.schemas import (
    ReviewIn,
    ReviewListOut,
    ReviewModerateIn,
    ReviewOut,
    ReviewReplyIn,
)
from app.services.audit import record_audit
from app.services.pagination import clamp_page_size, count_rows, envelope

log = logging.getLogger(__name__)
router = APIRouter(tags=["reviews"])

_SELECT = (
    "SELECT r.id, r.product_id, r.user_id, r.rating, r.title, r.body, r.status, "
    "r.seller_reply, r.seller_replied_at, r.created_at, p.full_name AS author_name "
    "FROM public.product_reviews r "
    "LEFT JOIN public.profiles p ON p.id = r.user_id"
)


def _to_out(row) -> ReviewOut:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["seller_replied_at"] = (
        d["seller_replied_at"].isoformat() if d.get("seller_replied_at") else None
    )
    return ReviewOut(**d)


@router.get("/products/{product_id}/reviews", response_model=ReviewListOut)
async def list_reviews(
    product_id: str,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewListOut:
    summary = (
        await session.execute(
            text(
                "SELECT AVG(rating)::float AS average, COUNT(*) AS count "
                "FROM public.product_reviews "
                "WHERE product_id = :pid AND status = 'published'"
            ),
            {"pid": product_id},
        )
    ).mappings().first()

    dist_rows = (
        await session.execute(
            text(
                "SELECT rating, COUNT(*) AS n FROM public.product_reviews "
                "WHERE product_id = :pid AND status = 'published' GROUP BY rating"
            ),
            {"pid": product_id},
        )
    ).mappings().all()
    distribution = {i: 0 for i in range(1, 6)}
    for r in dist_rows:
        distribution[int(r["rating"])] = int(r["n"])

    rows = (
        await session.execute(
            text(
                _SELECT
                + " WHERE r.product_id = :pid AND r.status = 'published' "
                "ORDER BY r.created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"pid": product_id, "limit": limit, "offset": offset},
        )
    ).mappings().all()

    return ReviewListOut(
        product_id=product_id,
        average=float(summary["average"]) if summary and summary["average"] else None,
        count=int(summary["count"]) if summary else 0,
        distribution=distribution,
        reviews=[_to_out(r) for r in rows],
    )


@router.post(
    "/products/{product_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_review(
    product_id: str, body: ReviewIn, user: CurrentUser, session: DbSession
) -> ReviewOut:
    exists = (
        await session.execute(
            text("SELECT 1 FROM public.products WHERE id = :pid"), {"pid": product_id}
        )
    ).first()
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")

    row = (
        await session.execute(
            text(
                "INSERT INTO public.product_reviews "
                "(product_id, user_id, rating, title, body) "
                "VALUES (:pid, :uid, :rating, :title, :body) "
                "ON CONFLICT (product_id, user_id) DO UPDATE SET "
                "  rating = EXCLUDED.rating, title = EXCLUDED.title, "
                "  body = EXCLUDED.body, updated_at = now() "
                "RETURNING id"
            ),
            {
                "pid": product_id,
                "uid": str(user.id),
                "rating": body.rating,
                "title": body.title,
                "body": body.body,
            },
        )
    ).mappings().first()
    await session.commit()

    full = (
        await session.execute(
            text(_SELECT + " WHERE r.id = :rid"), {"rid": str(row["id"])}
        )
    ).mappings().first()
    return _to_out(full)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: UUID, user: CurrentUser, session: DbSession
) -> None:
    row = (
        await session.execute(
            text("SELECT user_id FROM public.product_reviews WHERE id = :rid"),
            {"rid": str(review_id)},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نظر پیدا نشد")
    if str(row[0]) != str(user.id) and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی مجاز نیست")
    await session.execute(
        text("DELETE FROM public.product_reviews WHERE id = :rid"),
        {"rid": str(review_id)},
    )
    if user.is_admin:
        await record_audit(
            session,
            admin_id=user.id,
            action="delete_review",
            entity_type="review",
            entity_id=str(review_id),
        )
    await session.commit()


@router.get("/admin/reviews")
async def admin_list_reviews(
    session: DbSession,
    user: StaffReviews,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
) -> list[ReviewOut] | dict:
    base_sql = _SELECT
    params: dict = {}
    if status_filter:
        base_sql += " WHERE r.status = :status"
        params["status"] = status_filter
    page, page_size = clamp_page_size(page, page_size, default_size=20)
    sql = base_sql + " ORDER BY r.created_at DESC"
    total = 0
    if page > 0:
        total = await count_rows(session, base_sql, params)
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    else:
        sql += " LIMIT :limit"
        params["limit"] = limit
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [_to_out(r) for r in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
async def moderate_or_reply(
    review_id: UUID,
    body: ReviewModerateIn | ReviewReplyIn,
    user: StaffReviews,
    session: DbSession,
) -> ReviewOut:
    """Admin: hide/publish a review and/or post the seller's reply."""
    if isinstance(body, ReviewModerateIn):
        sets = ["status = :status"]
        params: dict = {"status": body.status}
    else:
        sets = ["seller_reply = :reply", "seller_replied_at = now()"]
        params = {"reply": body.seller_reply}
    params["rid"] = str(review_id)

    row = (
        await session.execute(
            text(
                f"UPDATE public.product_reviews SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = :rid RETURNING id"
            ),
            params,
        )
    ).mappings().first()
    if row is None:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نظر پیدا نشد")

    if isinstance(body, ReviewModerateIn):
        await record_audit(
            session,
            admin_id=user.id,
            action="moderate_review",
            entity_type="review",
            entity_id=str(review_id),
            new_values={"status": body.status},
        )

    await session.commit()

    full = (
        await session.execute(
            text(_SELECT + " WHERE r.id = :rid"), {"rid": str(row["id"])}
        )
    ).mappings().first()
    return _to_out(full)
