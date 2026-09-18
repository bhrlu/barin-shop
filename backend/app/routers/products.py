"""Product catalog endpoints.

GET /products, GET /products/{id}  — public (active only for anonymous callers)
POST/PATCH/DELETE /products[/{id}] — admin only

Admin delete: soft-deletes (active=false) if the product has been ordered;
hard-deletes otherwise (keeps order history intact either way).
"""

import json
import logging
import uuid
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text

from app.auth import AdminUser, AuthUser, DbSession
from app.schemas import ProductIn, ProductOut, ProductUpdateIn
from app.security import decode_access_token
from app.services.roles import resolve_role

log = logging.getLogger(__name__)
router = APIRouter(tags=["products"])

_SELECT = (
    "SELECT id, name, category, price, old_price, sizes, colors, images, "
    "material, description, is_new, stock, active, created_at, updated_at "
    "FROM public.products"
)

_RETURNING = (
    "RETURNING id, name, category, price, old_price, sizes, colors, images, "
    "material, description, is_new, stock, active, created_at, updated_at"
)


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
    return ProductOut(**d)


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    session: DbSession,
    category: str | None = None,
    include_inactive: bool = False,
    user: Annotated[AuthUser | None, Depends(_optional_admin)] = None,
) -> list[ProductOut]:
    """Public list. Admins may pass include_inactive=true with a valid token."""
    sql = _SELECT
    conditions = []
    params: dict[str, Any] = {}

    is_admin = user is not None and getattr(user, "is_admin", False)
    if not is_admin or not include_inactive:
        conditions.append("active = true")

    if category:
        conditions.append("category = :category")
        params["category"] = category

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at ASC"

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [_row_to_out(row) for row in rows]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, session: DbSession) -> ProductOut:
    row = (
        await session.execute(text(_SELECT + " WHERE id = :pid"), {"pid": product_id})
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return _row_to_out(row)


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductIn, session: DbSession, user: AdminUser) -> ProductOut:
    pid = str(uuid.uuid4())
    try:
        row = (
            await session.execute(
                text(
                    "INSERT INTO public.products "
                    "(id, name, category, price, old_price, sizes, colors, images, "
                    " material, description, is_new, stock, active) "
                    "VALUES (:id, :name, :category, :price, :old_price, "
                    "        CAST(:sizes AS text[]), CAST(:colors AS jsonb), "
                    "        CAST(:images AS text[]), :material, :description, "
                    "        :is_new, :stock, :active) " + _RETURNING
                ),
                {"id": pid, **_payload(body)},
            )
        ).mappings().first()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("product insert failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ذخیره محصول ناموفق بود") from exc
    return _row_to_out(row)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, body: ProductUpdateIn, session: DbSession, user: AdminUser
) -> ProductOut:
    sets, params = _update_sets(body)
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    params["pid"] = product_id
    try:
        row = (
            await session.execute(
                text(
                    f"UPDATE public.products SET {', '.join(sets)}, updated_at = now() "
                    f"WHERE id = :pid {_RETURNING}"
                ),
                params,
            )
        ).mappings().first()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.exception("product update failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "به‌روزرسانی محصول ناموفق بود") from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return _row_to_out(row)


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
    return sets, params
