"""Product catalog endpoints.

Public:
  GET  /products                   — list with filters + sorting
  GET  /products/compare           — side-by-side comparison for ids=
  GET  /products/{id}              — one product
  GET  /products/{id}/related      — same-category picks
  GET  /products/{id}/recommendations
  GET  /products/{id}/variants     — per size×color stock
  GET  /recently-viewed            — signed-in customer's history
  POST /products/{id}/view         — record a view

Admin (requires admin role):
  POST/PATCH/DELETE /products[/{id}]
  POST   /products/{id}/variants
  PATCH  /variants/{variant_id}
  DELETE /variants/{variant_id}

Admin delete: soft-deletes (active=false) if the product has been ordered;
hard-deletes otherwise (keeps order history intact either way).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text

from app.auth import AdminUser, AuthUser, CurrentUser, DbSession
from app.schemas import (
    ProductIn,
    ProductOut,
    ProductUpdateIn,
    ProductVariantIn,
    ProductVariantOut,
    ProductVariantUpdateIn,
)
from app.security import decode_access_token
from app.services.catalog_filters import split_multi
from app.services.roles import resolve_role

log = logging.getLogger(__name__)
router = APIRouter(tags=["products"])

# Rating summary is folded into every product read so cards can show stars
# without a second request. Small catalog → the correlated subqueries are cheap.
_PRODUCT_COLS = (
    "p.id, p.name, p.category, p.price, p.old_price, p.sizes, p.colors, p.images, "
    "p.material, p.description, p.is_new, p.stock, p.active, p.tags, p.badge, "
    "p.availability, p.available_at, p.low_stock_threshold, p.created_at, p.updated_at, "
    "(SELECT AVG(r.rating)::float FROM public.product_reviews r "
    " WHERE r.product_id = p.id AND r.status = 'published') AS avg_rating, "
    "(SELECT COUNT(*) FROM public.product_reviews r "
    " WHERE r.product_id = p.id AND r.status = 'published') AS review_count"
)

_SELECT = f"SELECT {_PRODUCT_COLS} FROM public.products p"

_VARIANT_COLS = (
    "id, product_id, size, color, sku, stock, active, created_at, updated_at"
)

SortKey = Literal["new", "price_asc", "price_desc", "popular", "rating"]

_SORTS = {
    "new": "p.created_at DESC",
    "price_asc": "p.price ASC",
    "price_desc": "p.price DESC",
    "popular": "review_count DESC NULLS LAST, p.is_new DESC, p.created_at DESC",
    "rating": "avg_rating DESC NULLS LAST, review_count DESC NULLS LAST",
}

_bearer = HTTPBearer(auto_error=False)


async def _optional_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: DbSession,
) -> AuthUser | None:
    """Resolve the caller when a valid token is presented; anonymous otherwise."""
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        sub = payload.get("sub")
        if not sub:
            return None
        role = await resolve_role(session, UUID(sub))
    except (JWTError, ValueError):
        return None
    return AuthUser(UUID(sub), payload.get("email"), role)


def _row_to_out(row) -> ProductOut:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
    d["available_at"] = d["available_at"].isoformat() if d.get("available_at") else None
    d["tags"] = list(d.get("tags") or [])
    d["review_count"] = int(d.get("review_count") or 0)
    if d.get("avg_rating") is not None:
        d["avg_rating"] = float(d["avg_rating"])
    return ProductOut(**d)


def _variant_to_out(row) -> ProductVariantOut:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
    return ProductVariantOut(**d)


async def _fetch_product(session, product_id: str) -> ProductOut | None:
    row = (
        await session.execute(
            text(_SELECT + " WHERE p.id = :pid"), {"pid": product_id}
        )
    ).mappings().first()
    return _row_to_out(row) if row else None


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    session: DbSession,
    category: str | None = None,
    tag: str | None = None,
    badge: str | None = None,
    availability: str | None = None,
    on_sale: bool = False,
    size: Annotated[
        list[str] | None,
        Query(description="repeatable and/or comma-separated sizes, e.g. ?size=M,L&size=XL"),
    ] = None,
    color: Annotated[
        list[str] | None,
        Query(description="repeatable and/or comma-separated colour names"),
    ] = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    sort: SortKey = "new",
    include_inactive: bool = False,
    user: Annotated[AuthUser | None, Depends(_optional_admin)] = None,
) -> list[ProductOut]:
    """Public list. Admins may pass include_inactive=true with a valid token."""
    sql = _SELECT
    conditions: list[str] = []
    params: dict[str, Any] = {}

    is_admin = user is not None and getattr(user, "is_admin", False)
    if not is_admin or not include_inactive:
        conditions.append("p.active = true")

    if category:
        conditions.append("p.category = :category")
        params["category"] = category
    if tag:
        conditions.append(":tag = ANY(p.tags)")
        params["tag"] = tag
    if badge:
        conditions.append("p.badge = :badge")
        params["badge"] = badge
    if availability:
        conditions.append("p.availability = :availability")
        params["availability"] = availability
    if on_sale:
        conditions.append("p.old_price IS NOT NULL")
    # Size and colour are OR within their own facet and AND across facets. When
    # both are given the match is resolved **per combination**: at least one
    # requested size × colour pair must still be purchasable, so a pair the admin
    # deactivated with a variant row does not count as offered.
    sizes = split_multi(size)
    colors = split_multi(color)
    if sizes and colors:
        conditions.append(
            "EXISTS (SELECT 1 FROM unnest(p.sizes) AS s "
            "CROSS JOIN LATERAL jsonb_array_elements(p.colors) AS c "
            "WHERE s = ANY(:sizes) AND c->>'name' = ANY(:colors) "
            "  AND NOT EXISTS (SELECT 1 FROM public.product_variants v "
            "                  WHERE v.product_id = p.id AND v.size = s "
            "                    AND v.color = c->>'name' AND NOT v.active))"
        )
        params["sizes"] = sizes
        params["colors"] = colors
    elif sizes:
        conditions.append("p.sizes && CAST(:sizes AS text[])")
        params["sizes"] = sizes
    elif colors:
        conditions.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements(p.colors) c "
            "WHERE c->>'name' = ANY(:colors))"
        )
        params["colors"] = colors
    if min_price is not None:
        conditions.append("p.price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        conditions.append("p.price <= :max_price")
        params["max_price"] = max_price

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY " + _SORTS.get(sort, _SORTS["new"])

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [_row_to_out(row) for row in rows]


@router.get("/products/compare", response_model=list[ProductOut])
async def compare_products(
    session: DbSession,
    ids: str = Query(..., min_length=1, description="comma-separated product ids"),
) -> list[ProductOut]:
    """Return the requested products in the order given (missing ids skipped)."""
    wanted = [i.strip() for i in ids.split(",") if i.strip()]
    if not wanted:
        return []
    if len(wanted) > 10:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "حداکثر ۱۰ محصول قابل مقایسه است")

    rows = (
        await session.execute(
            text(_SELECT + " WHERE p.id = ANY(:ids)"), {"ids": wanted}
        )
    ).mappings().all()
    by_id = {r["id"]: _row_to_out(r) for r in rows}
    return [by_id[pid] for pid in wanted if pid in by_id]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, session: DbSession) -> ProductOut:
    product = await _fetch_product(session, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return product


@router.get("/products/{product_id}/related", response_model=list[ProductOut])
async def related_products(
    product_id: str, session: DbSession, limit: int = Query(default=4, ge=1, le=20)
) -> list[ProductOut]:
    rows = (
        await session.execute(
            text(
                _SELECT
                + " WHERE p.active AND p.category = "
                "(SELECT category FROM public.products WHERE id = :pid) "
                "  AND p.id <> :pid "
                "ORDER BY p.is_new DESC, review_count DESC NULLS LAST, p.created_at DESC "
                "LIMIT :limit"
            ),
            {"pid": product_id, "limit": limit},
        )
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


@router.get("/products/{product_id}/recommendations", response_model=list[ProductOut])
async def recommended_products(
    product_id: str, session: DbSession, limit: int = Query(default=4, ge=1, le=20)
) -> list[ProductOut]:
    """Same category first, then the rest of the catalog; never the product itself."""
    rows = (
        await session.execute(
            text(
                _SELECT
                + " WHERE p.active AND p.id <> :pid "
                "ORDER BY (p.category = "
                "(SELECT category FROM public.products WHERE id = :pid)) DESC, "
                "  review_count DESC NULLS LAST, p.is_new DESC, p.created_at DESC "
                "LIMIT :limit"
            ),
            {"pid": product_id, "limit": limit},
        )
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


@router.post("/products/{product_id}/view", status_code=status.HTTP_202_ACCEPTED)
async def record_view(product_id: str, user: CurrentUser, session: DbSession) -> dict:
    exists = await _fetch_product(session, product_id)
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    await session.execute(
        text(
            "INSERT INTO public.recently_viewed (user_id, product_id) "
            "VALUES (:uid, :pid) "
            "ON CONFLICT (user_id, product_id) DO UPDATE SET viewed_at = now()"
        ),
        {"uid": str(user.id), "pid": product_id},
    )
    await session.commit()
    return {"ok": True}


@router.get("/recently-viewed", response_model=list[ProductOut])
async def recently_viewed(
    user: CurrentUser, session: DbSession, limit: int = Query(default=10, ge=1, le=50)
) -> list[ProductOut]:
    rows = (
        await session.execute(
            text(
                _SELECT
                + " JOIN public.recently_viewed rv ON rv.product_id = p.id "
                "WHERE rv.user_id = :uid AND p.active "
                "ORDER BY rv.viewed_at DESC LIMIT :limit"
            ),
            {"uid": str(user.id), "limit": limit},
        )
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


# --- variants -------------------------------------------------------------------


@router.get("/products/{product_id}/variants", response_model=list[ProductVariantOut])
async def list_variants(product_id: str, session: DbSession) -> list[ProductVariantOut]:
    rows = (
        await session.execute(
            text(
                f"SELECT {_VARIANT_COLS} FROM public.product_variants "
                "WHERE product_id = :pid ORDER BY size, color"
            ),
            {"pid": product_id},
        )
    ).mappings().all()
    return [_variant_to_out(r) for r in rows]


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    product_id: str, body: ProductVariantIn, session: DbSession, user: AdminUser
) -> ProductVariantOut:
    if await _fetch_product(session, product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    try:
        row = (
            await session.execute(
                text(
                    "INSERT INTO public.product_variants "
                    "(product_id, size, color, sku, stock, active) "
                    "VALUES (:pid, :size, :color, :sku, :stock, :active) "
                    f"RETURNING {_VARIANT_COLS}"
                ),
                {
                    "pid": product_id,
                    "size": body.size,
                    "color": body.color,
                    "sku": body.sku,
                    "stock": body.stock,
                    "active": body.active,
                },
            )
        ).mappings().first()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("variant insert failed")
        raise HTTPException(
            status.HTTP_409_CONFLICT, "این ترکیب سایز و رنگ قبلاً ثبت شده است"
        ) from exc
    return _variant_to_out(row)


@router.patch("/variants/{variant_id}", response_model=ProductVariantOut)
async def update_variant(
    variant_id: UUID, body: ProductVariantUpdateIn, session: DbSession, user: AdminUser
) -> ProductVariantOut:
    sets: list[str] = []
    params: dict[str, Any] = {"vid": str(variant_id)}
    for field in ("size", "color", "sku", "stock", "active"):
        value = getattr(body, field)
        if value is not None:
            sets.append(f"{field} = :{field}")
            params[field] = value
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    try:
        row = (
            await session.execute(
                text(
                    f"UPDATE public.product_variants SET {', '.join(sets)}, "
                    f"updated_at = now() WHERE id = :vid RETURNING {_VARIANT_COLS}"
                ),
                params,
            )
        ).mappings().first()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("variant update failed")
        raise HTTPException(
            status.HTTP_409_CONFLICT, "به‌روزرسانی تنوع ناموفق بود"
        ) from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تنوع پیدا نشد")
    return _variant_to_out(row)


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(variant_id: UUID, session: DbSession, user: AdminUser) -> None:
    result = await session.execute(
        text("DELETE FROM public.product_variants WHERE id = :vid"),
        {"vid": str(variant_id)},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تنوع پیدا نشد")


# --- admin CRUD -------------------------------------------------------------------


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductIn, session: DbSession, user: AdminUser) -> ProductOut:
    pid = str(uuid.uuid4())
    try:
        await session.execute(
            text(
                "INSERT INTO public.products "
                "(id, name, category, price, old_price, sizes, colors, images, "
                " material, description, is_new, stock, active, tags, badge, "
                " availability, available_at, low_stock_threshold) "
                "VALUES (:id, :name, :category, :price, :old_price, "
                "        CAST(:sizes AS text[]), CAST(:colors AS jsonb), "
                "        CAST(:images AS text[]), :material, :description, "
                "        :is_new, :stock, :active, CAST(:tags AS text[]), :badge, "
                "        :availability, :available_at, :low_stock_threshold)"
            ),
            {"id": pid, **_payload(body)},
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("product insert failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ذخیره محصول ناموفق بود") from exc
    product = await _fetch_product(session, pid)
    assert product is not None
    return product


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, body: ProductUpdateIn, session: DbSession, user: AdminUser
) -> ProductOut:
    sets, params = _update_sets(body)
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    params["pid"] = product_id
    try:
        await session.execute(
            text(
                f"UPDATE public.products SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = :pid"
            ),
            params,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("product update failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "به‌روزرسانی محصول ناموفق بود") from exc
    product = await _fetch_product(session, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, session: DbSession, user: AdminUser) -> None:
    ordered = (
        await session.execute(
            text("SELECT 1 FROM public.order_items WHERE product_id = :pid LIMIT 1"),
            {"pid": product_id},
        )
    ).first()
    if ordered is not None:
        # keep history intact — hide the product instead of deleting
        await session.execute(
            text("UPDATE public.products SET active = false, updated_at = now() WHERE id = :pid"),
            {"pid": product_id},
        )
    else:
        await session.execute(
            text("DELETE FROM public.products WHERE id = :pid"), {"pid": product_id}
        )
    await session.commit()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "تاریخ نامعتبر است"
        ) from exc


def _payload(body: ProductIn) -> dict:
    return {
        "name": body.name,
        "category": body.category,
        "price": body.price,
        "old_price": body.old_price,
        "sizes": body.sizes,
        "colors": json.dumps([c.model_dump() for c in body.colors], ensure_ascii=False),
        "images": body.images,
        "material": body.material,
        "description": body.description,
        "is_new": body.is_new,
        "stock": body.stock,
        "active": body.active,
        "tags": body.tags,
        "badge": body.badge,
        "availability": body.availability,
        "available_at": _parse_dt(body.available_at),
        "low_stock_threshold": body.low_stock_threshold,
    }


def _update_sets(body: ProductUpdateIn) -> tuple[list[str], dict[str, Any]]:
    sets: list[str] = []
    params: dict[str, Any] = {}
    if body.name is not None:
        sets.append("name = :name")
        params["name"] = body.name
    if body.category is not None:
        sets.append("category = :category")
        params["category"] = body.category
    if body.price is not None:
        sets.append("price = :price")
        params["price"] = body.price
    if "old_price" in body.model_fields_set:
        sets.append("old_price = :old_price")
        params["old_price"] = body.old_price
    if body.sizes is not None:
        sets.append("sizes = CAST(:sizes AS text[])")
        params["sizes"] = body.sizes
    if body.colors is not None:
        sets.append("colors = CAST(:colors AS jsonb)")
        params["colors"] = json.dumps([c.model_dump() for c in body.colors], ensure_ascii=False)
    if body.images is not None:
        sets.append("images = CAST(:images AS text[])")
        params["images"] = body.images
    if body.material is not None:
        sets.append("material = :material")
        params["material"] = body.material
    if body.description is not None:
        sets.append("description = :description")
        params["description"] = body.description
    if body.is_new is not None:
        sets.append("is_new = :is_new")
        params["is_new"] = body.is_new
    if body.stock is not None:
        sets.append("stock = :stock")
        params["stock"] = body.stock
    if body.active is not None:
        sets.append("active = :active")
        params["active"] = body.active
    if body.tags is not None:
        sets.append("tags = CAST(:tags AS text[])")
        params["tags"] = body.tags
    if "badge" in body.model_fields_set:
        sets.append("badge = :badge")
        params["badge"] = body.badge
    if body.availability is not None:
        sets.append("availability = :availability")
        params["availability"] = body.availability
    if "available_at" in body.model_fields_set:
        sets.append("available_at = :available_at")
        params["available_at"] = _parse_dt(body.available_at)
    if body.low_stock_threshold is not None:
        sets.append("low_stock_threshold = :low_stock_threshold")
        params["low_stock_threshold"] = body.low_stock_threshold
    return sets, params
