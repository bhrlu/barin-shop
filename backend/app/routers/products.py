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

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, DbSession, OptionalUser, StaffCatalog
from app.schemas import (
    ProductColor,
    ProductFacets,
    ProductIn,
    ProductOut,
    ProductUpdateIn,
    ProductVariantIn,
    ProductVariantOut,
    ProductVariantUpdateIn,
)
from app.services import csv_import
from app.services.audit import record_audit
from app.services.catalog_filters import split_multi
from app.services.db_errors import is_unique_violation, violated_constraint
from app.services.inventory_log import log_stock_change
from app.services.pagination import apply_limit_offset, clamp_page_size, count_rows, envelope
from app.services.recommendations import CO_VOTES_SQL
from app.services.roles import has_capability

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
    "id, product_id, size, color, sku, stock, active, price_override, color_hex, "
    "created_at, updated_at"
)
_SKU_TAKEN = "این SKU قبلاً برای تنوع دیگری ثبت شده است"


def _variant_conflict(exc: IntegrityError, fallback: str) -> HTTPException:
    """409 for a duplicate; which rule was hit decides the message (AB-BE-02)."""
    if violated_constraint(exc) == "product_variants_sku_key":
        return HTTPException(status.HTTP_409_CONFLICT, _SKU_TAKEN)
    return HTTPException(status.HTTP_409_CONFLICT, fallback)

SortKey = Literal["new", "price_asc", "price_desc", "popular", "rating"]

_SORTS = {
    "new": "p.created_at DESC",
    "price_asc": "p.price ASC",
    "price_desc": "p.price DESC",
    "popular": "review_count DESC NULLS LAST, p.is_new DESC, p.created_at DESC",
    "rating": "avg_rating DESC NULLS LAST, review_count DESC NULLS LAST",
}

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


@router.get("/products")
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
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
    user: OptionalUser = None,
) -> list[ProductOut] | dict:
    """Public list. Staff with the `catalog` capability may pass include_inactive=true.

    Bare list by default; pass `page` (and optional `page_size`) to get the
    `{items, total, page, page_size, pages}` envelope (F2.5)."""
    sql = _SELECT
    conditions: list[str] = []
    params: dict[str, Any] = {}

    # B5.4b: whoever may edit the catalog (order_manager included) must also see
    # the inactive rows — it used to be admin/super_admin only (`is_admin`)
    can_see_inactive = user is not None and has_capability(user.roles, "catalog")
    if not can_see_inactive or not include_inactive:
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

    # F2.5: envelope only when the caller asks for a page
    page, page_size = clamp_page_size(page, page_size, default_size=12)
    if page > 0:
        base = sql[: sql.rindex(" ORDER BY ")]
        total = await count_rows(session, base, params)
        sql = apply_limit_offset(sql, page, page_size)

    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [_row_to_out(row) for row in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.get("/products/facets", response_model=ProductFacets)
async def product_facets(session: DbSession) -> ProductFacets:
    """Filter options for `/shop`: the sizes, colours and tags of the active catalogue
    (first-seen order over the newest-first list) and its price range (F5.8).

    The storefront used to download every product — and sign every image — to build
    these. Inactive products never contribute, whoever asks."""
    rows = (
        await session.execute(
            text(
                "SELECT sizes, colors, tags, price FROM public.products "
                "WHERE active = true ORDER BY created_at DESC, id"
            )
        )
    ).mappings().all()
    sizes: dict[str, None] = {}
    colors: dict[str, ProductColor] = {}  # by name: first position, last hex
    tags: dict[str, None] = {}
    for row in rows:
        sizes.update(dict.fromkeys(row["sizes"] or []))
        for color in row["colors"] or []:
            if isinstance(color, dict) and color.get("name"):
                colors[color["name"]] = ProductColor(name=color["name"], hex=color.get("hex", ""))
        tags.update(dict.fromkeys(row["tags"] or []))
    prices = [row["price"] for row in rows]
    return ProductFacets(
        sizes=list(sizes),
        colors=list(colors.values()),
        tags=list(tags),
        price_min=min(prices, default=None),
        price_max=max(prices, default=None),
    )


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
    """Co-purchase blend (B2.4): learned "bought together" votes (weight 3) on
    top of the category/popularity heuristic; pure heuristic when no pair data
    exists yet. Never the product itself."""
    rows = (
        await session.execute(
            text(
                "SELECT "
                + _PRODUCT_COLS
                + ", ("
                + CO_VOTES_SQL
                + " ) * 3 "
                "  + CASE WHEN p.category = (SELECT category FROM public.products WHERE id = :pid) "
                "         THEN 100 ELSE 0 END "
                "  + (SELECT COUNT(*) FROM public.product_reviews r "
                "     WHERE r.product_id = p.id AND r.status = 'published') * 2 "
                "  + CASE WHEN p.is_new THEN 10 ELSE 0 END + 5 AS score "
                "FROM public.products p "
                "WHERE p.active AND p.id <> :pid "
                "ORDER BY score DESC, p.created_at DESC LIMIT :limit"
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
    product_id: str, body: ProductVariantIn, session: DbSession, user: StaffCatalog
) -> ProductVariantOut:
    if await _fetch_product(session, product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    try:
        row = (
            await session.execute(
                text(
                    "INSERT INTO public.product_variants "
                    "(product_id, size, color, sku, stock, active, price_override, color_hex) "
                    "VALUES (:pid, :size, :color, :sku, :stock, :active, :price, :hex) "
                    f"RETURNING {_VARIANT_COLS}"
                ),
                {
                    "pid": product_id,
                    "size": body.size,
                    "color": body.color,
                    "sku": body.sku,
                    "stock": body.stock,
                    "active": body.active,
                    "price": body.price_override,
                    "hex": body.color_hex,
                },
            )
        ).mappings().first()
        await record_audit(
            session,
            admin_id=user.id,
            action="create_variant",
            entity_type="variant",
            entity_id=str(row["id"]),
            new_values={
                "product_id": product_id,
                "size": body.size,
                "color": body.color,
                "stock": body.stock,
                "sku": body.sku,
                "price_override": body.price_override,
                "color_hex": body.color_hex,
            },
        )
        await log_stock_change(
            session,
            product_id=product_id,
            variant_id=row["id"],
            change=body.stock,
            reason="restock",
            actor_id=user.id,
        )
        await session.commit()
    except IntegrityError as exc:
        # only the real duplicate (UNIQUE product_id, size, color) is a 409;
        # anything else is a fault and surfaces as a 500 (B6.9a)
        await session.rollback()
        if not is_unique_violation(exc):
            log.exception("variant insert failed with an unexpected integrity error")
            raise
        raise _variant_conflict(exc, "این ترکیب سایز و رنگ قبلاً ثبت شده است") from exc
    return _variant_to_out(row)


@router.patch("/variants/{variant_id}", response_model=ProductVariantOut)
async def update_variant(
    variant_id: UUID, body: ProductVariantUpdateIn, session: DbSession, user: StaffCatalog
) -> ProductVariantOut:
    sets: list[str] = []
    params: dict[str, Any] = {"vid": str(variant_id)}
    for field in ("size", "color", "sku", "stock", "active", "price_override", "color_hex"):
        value = getattr(body, field)
        if value is not None:
            sets.append(f"{field} = :{field}")
            # the clear values (F5.16 convention) store NULL
            cleared = value == "" if field in ("sku", "color_hex") else (
                field == "price_override" and value == 0
            )
            params[field] = None if cleared else value
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    before = (
        await session.execute(
            text(
                f"SELECT {_VARIANT_COLS} FROM public.product_variants "
                "WHERE id = :vid FOR UPDATE"
            ),
            {"vid": str(variant_id)},
        )
    ).mappings().first()
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
        if before is not None and row is not None:
            await record_audit(
                session,
                admin_id=user.id,
                action="update_variant",
                entity_type="variant",
                entity_id=str(variant_id),
                old_values={k: before[k] for k in params if k != "vid"},
                new_values={k: row[k] for k in params if k != "vid"},
            )
            if "stock" in params:
                await log_stock_change(
                    session,
                    product_id=row["product_id"],
                    variant_id=variant_id,
                    change=int(row["stock"]) - int(before["stock"]),
                    reason="manual_adjustment",
                    actor_id=user.id,
                )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if not is_unique_violation(exc):
            log.exception("variant update failed with an unexpected integrity error")
            raise
        raise _variant_conflict(exc, "این ترکیب سایز و رنگ قبلاً ثبت شده است") from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تنوع پیدا نشد")
    return _variant_to_out(row)


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(variant_id: UUID, session: DbSession, user: StaffCatalog) -> None:
    result = await session.execute(
        text("DELETE FROM public.product_variants WHERE id = :vid"),
        {"vid": str(variant_id)},
    )
    if result.rowcount:
        await record_audit(
            session,
            admin_id=user.id,
            action="delete_variant",
            entity_type="variant",
            entity_id=str(variant_id),
        )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تنوع پیدا نشد")


@router.post("/products/import", status_code=status.HTTP_200_OK)
async def import_products_csv(
    session: DbSession,
    user: StaffCatalog,
    file: UploadFile,
) -> dict[str, int]:
    """Bulk upsert from a CSV file (B2.2a, decision D3).

    The canonical key is a valid `product_id` when the file supplies one,
    otherwise the normalized `name + category`. Only supplied columns update;
    in-file duplicate keys and malformed cells are a 422 before anything is
    written; the whole file lands in one transaction, so a retried import is
    safe to repeat. Catalog staff only, like the other product mutations.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فایل CSV خالی است")
    report = await csv_import.import_rows(session, content, user.id)
    await record_audit(
        session,
        admin_id=user.id,
        action="import_products",
        entity_type="product",
        entity_id="bulk",
        new_values={
            "file": file.filename or "upload.csv",
            **report,
        },
    )
    await session.commit()
    return report


# --- admin CRUD -------------------------------------------------------------------


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductIn, session: DbSession, user: StaffCatalog) -> ProductOut:
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
        await record_audit(
            session,
            admin_id=user.id,
            action="create_product",
            entity_type="product",
            entity_id=pid,
            new_values={"name": body.name, "price": body.price, "stock": body.stock},
        )
        # AB-BE-01: the opening stock is the product's first ledger entry
        await log_stock_change(
            session, product_id=pid, change=body.stock, reason="restock", actor_id=user.id
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if not is_unique_violation(exc):
            log.exception("product insert failed with an unexpected integrity error")
            raise
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ذخیره محصول ناموفق بود") from exc
    product = await _fetch_product(session, pid)
    assert product is not None
    return product


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, body: ProductUpdateIn, session: DbSession, user: StaffCatalog
) -> ProductOut:
    sets, params = _update_sets(body)
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "چیزی برای به‌روزرسانی نیست")

    params["pid"] = product_id
    # locked: a checkout between this read and the UPDATE would make the ledger's
    # delta (new − old) wrong (AB-BE-01)
    before = (
        await session.execute(
            text(
                "SELECT name, price, stock, active FROM public.products "
                "WHERE id = :pid FOR UPDATE"
            ),
            {"pid": product_id},
        )
    ).mappings().first()
    try:
        await session.execute(
            text(
                f"UPDATE public.products SET {', '.join(sets)}, updated_at = now() "
                "WHERE id = :pid"
            ),
            params,
        )
        if before is not None:
            tracked = ("name", "price", "stock", "active")
            await record_audit(
                session,
                admin_id=user.id,
                action="update_product",
                entity_type="product",
                entity_id=product_id,
                old_values={k: before[k] for k in tracked if k in params},
                new_values={
                    k: params[k] for k in tracked if k in params
                },
            )
            if "stock" in params:
                await log_stock_change(
                    session,
                    product_id=product_id,
                    change=int(params["stock"]) - int(before["stock"]),
                    reason="manual_adjustment",
                    actor_id=user.id,
                )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if not is_unique_violation(exc):
            log.exception("product update failed with an unexpected integrity error")
            raise
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "به‌روزرسانی محصول ناموفق بود") from exc
    product = await _fetch_product(session, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, session: DbSession, user: StaffCatalog) -> None:
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
        await record_audit(
            session,
            admin_id=user.id,
            action="delete_product",
            entity_type="product",
            entity_id=product_id,
            old_values={"active": True},
            new_values={"active": False},
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
