"""CSV product import (B2.2a, decision D3).

One endpoint, one transaction, deterministic results:

* the canonical key is a valid `product_id` (UUID) when the CSV supplies one —
  such a row is an id-keyed upsert and never falls back to name matching —
  otherwise the normalized `name + category` pair (trim, case-fold, collapse
  internal whitespace, so «شومیز» and «  شومیز  » match);
* a row updates only the columns it actually supplies — an omitted column never
  erases the stored value; empty cells (or `N/A`/`-`/`null`) mean "not supplied";
* duplicate canonical keys inside one file are rejected (422) before anything
  is written — an ambiguous file must never be applied unpredictably;
* the whole file lands in ONE transaction: any failure rolls everything back,
  so a retried import either fully repeats its effect or does nothing —
  the upsert itself makes a successful import idempotent;
* new products get their opening stock as a `restock` ledger row through
  `services.inventory_log.log_stock_change` (the same as manual creation); an
  update that changes `stock` writes a `manual_adjustment` delta row;
* the router records one `import_products` audit entry with the counts.

CSV columns (header row required, BOM tolerated; unknown columns are rejected so
a mistyped header cannot silently drop data):

    product_id, name, category, price, old_price, stock, low_stock_threshold,
    active, sizes, colors, tags, badge, availability, available_at, material,
    description, is_new, images

`product_id`, `name`, `category` are the key columns (`name`/`category` are
required when `product_id` is absent, as is `price` for a new product); `colors`
accepts `Name:#hex` pairs separated by `|`; `sizes`/`tags`/`images` use `|`.
"""

import csv
import io
import json
import logging
import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import text

from app.services.inventory_log import log_stock_change

log = logging.getLogger(__name__)

IMPORT_COLUMNS = [
    "product_id", "name", "category", "price", "old_price", "stock",
    "low_stock_threshold", "active", "sizes", "colors", "tags", "badge",
    "availability", "available_at", "material", "description", "is_new", "images",
]

# "not supplied" for the optional columns: empty cell, whitespace, or a filler
_MISSING = {"", "n/a", "na", "-", "null", "none"}

BADGE_VALUES = {"sale", "coming_soon", "preorder", "new", "exclusive"}
AVAILABILITY_VALUES = {"in_stock", "coming_soon", "preorder"}

_TRUE = {"true", "1", "yes", "y", "بله"}
_FALSE = {"false", "0", "no", "n", "خیر"}


def _normalize(value: str | None) -> str:
    """D3 normalization: trim, case-fold, collapse internal whitespace."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _clean(value: str | None) -> str | None:
    """A supplied cell, or None when the column was omitted (D3: never erase)."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped.casefold() in _MISSING:
        return None
    return stripped


def _fail(row_no: int, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY, f"ردیف {row_no}: {message}"
    )


def _int(row: "_Row", column: str, required: bool = False) -> int | None:
    cleaned = _clean(row.get(column))
    if cleaned is None:
        if required:
            raise _fail(row.no, f"ستون «{column}» برای محصول جدید الزامی است")
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise _fail(row.no, f"«{column}» باید عدد باشد") from exc


def _bool(row: "_Row", column: str) -> bool | None:
    cleaned = _clean(row.get(column))
    if cleaned is None:
        return None
    folded = cleaned.casefold()
    if folded in _TRUE:
        return True
    if folded in _FALSE:
        return False
    raise _fail(row.no, f"«{column}» باید true یا false باشد")


def _enum(row: "_Row", column: str, allowed: set[str]) -> str | None:
    cleaned = _clean(row.get(column))
    if cleaned is None:
        return None
    if cleaned not in allowed:
        raise _fail(row.no, f"«{column}» باید یکی از {sorted(allowed)} باشد")
    return cleaned


def _dt(row: "_Row", column: str) -> datetime | None:
    cleaned = _clean(row.get(column))
    if cleaned is None:
        return None
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _fail(row.no, "تاریخ نامعتبر است") from exc


def _list(row: "_Row", column: str, separator: str = "|") -> list[str] | None:
    cleaned = _clean(row.get(column))
    if cleaned is None:
        return None
    return [part.strip() for part in cleaned.split(separator) if part.strip()]


def _colors(row: "_Row") -> list[dict[str, str]] | None:
    """`قرمز:#ff0000 | آبی:#0000ff` → the colors jsonb payload."""
    parts = _list(row, "colors")
    if parts is None:
        return None
    colors: list[dict[str, str]] = []
    for part in parts:
        name, sep, hexcode = part.partition(":")
        hexcode = hexcode.strip()
        if not sep or not name.strip() or not re.fullmatch(r"#?[0-9a-fA-F]{6}", hexcode):
            raise _fail(row.no, "رنگ‌ها باید به شکل «نام:#rrggbb» با | جدا شوند")
        colors.append(
            {
                "name": name.strip(),
                "hex": hexcode if hexcode.startswith("#") else f"#{hexcode}",
            }
        )
    return colors


class _Row:
    """One CSV record: raw cells plus the canonical key (D3)."""

    __slots__ = ("no", "cells", "key_id", "key_name", "key_category")

    def __init__(self, no: int, cells: dict[str, str]) -> None:
        self.no = no
        self.cells = cells
        product_id = _clean(cells.get("product_id"))
        if product_id is not None:
            try:
                UUID(product_id)
            except ValueError as exc:
                raise _fail(no, "product_id باید یک UUID معتبر باشد") from exc
        self.key_id = product_id
        self.key_name = _normalize(cells.get("name"))
        self.key_category = _normalize(cells.get("category"))
        if not product_id and (not self.key_name or not self.key_category):
            raise _fail(no, "بدون product_id، ستون‌های name و category الزامی‌اند")

    def canonical_key(self) -> tuple[str, str]:
        """The D3 key: id-keyed rows use ("id", <uuid>); the rest use the
        normalized name+category pair. The pair is the in-file duplicate key."""
        if self.key_id:
            return ("id", self.key_id.lower())
        return ("name+category", f"{self.key_name}\x1f{self.key_category}")

    def get(self, column: str) -> str | None:
        return self.cells.get(column)


def parse_csv(content: bytes) -> list[_Row]:
    """Decode (BOM tolerated), validate headers, and reject in-file duplicates (D3)."""
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "فایل باید UTF-8 باشد"
        ) from exc

    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فایل CSV خالی است")
    headers = [(name or "").strip().lstrip("\ufeff") for name in reader.fieldnames]
    unknown = [name for name in headers if name not in IMPORT_COLUMNS]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"ستون‌های ناشناس: {', '.join(unknown)}",
        )

    rows: list[_Row] = []
    seen: dict[tuple[str, str], int] = {}
    for row_no, raw in enumerate(reader, start=2):
        cells = {
            (key or "").strip().lstrip("\ufeff"): value
            for key, value in raw.items()
            if key is not None
        }
        if not any((value or "").strip() for value in cells.values()):
            continue  # a fully blank line is not a row
        row = _Row(row_no, cells)
        key = row.canonical_key()
        if key in seen:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"ردیف {row_no}: کلید تکراری با ردیف {seen[key]} در خود فایل "
                "(D3: فایل مبهم پذیرفته نمی‌شود)",
            )
        seen[key] = row_no
        rows.append(row)
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "هیچ ردیفی در فایل نیست")
    return rows


def _row_params(row: _Row) -> dict[str, Any]:
    """The column values this row actually supplies (D3: omitted ⇒ unchanged)."""
    params: dict[str, Any] = {}

    if (value := _clean(row.get("name"))) is not None:
        params["name"] = value
    if (value := _clean(row.get("category"))) is not None:
        params["category"] = value
    if (value := _int(row, "price")) is not None:
        params["price"] = value
    if (value := _int(row, "old_price")) is not None:
        params["old_price"] = value
    if (value := _int(row, "stock")) is not None:
        params["stock"] = value
    if (value := _int(row, "low_stock_threshold")) is not None:
        params["low_stock_threshold"] = value
    if (value := _bool(row, "active")) is not None:
        params["active"] = value
    if (value := _list(row, "sizes")) is not None:
        params["sizes"] = value
    if (value := _colors(row)) is not None:
        # the API binds jsonb payloads as JSON strings (same as POST /products)
        params["colors"] = json.dumps(value, ensure_ascii=False)
    if (value := _list(row, "tags")) is not None:
        params["tags"] = value
    if (value := _list(row, "images")) is not None:
        params["images"] = value
    if (value := _clean(row.get("material"))) is not None:
        params["material"] = value
    if (value := _clean(row.get("description"))) is not None:
        params["description"] = value
    if (value := _bool(row, "is_new")) is not None:
        params["is_new"] = value
    if (value := _enum(row, "badge", BADGE_VALUES)) is not None:
        params["badge"] = value
    if (value := _enum(row, "availability", AVAILABILITY_VALUES)) is not None:
        params["availability"] = value
    if (value := _dt(row, "available_at")) is not None:
        params["available_at"] = value
    return params


_CASTS = {
    "sizes": "CAST(:sizes AS text[])",
    "tags": "CAST(:tags AS text[])",
    "images": "CAST(:images AS text[])",
    "colors": "CAST(:colors AS jsonb)",
}


async def import_rows(session, content: bytes, actor_id) -> dict[str, int]:
    """Apply one import file in a single transaction (D3). Returns the report.

    Raises a 422 before writing anything when the file itself is invalid
    (headers, bad cell, in-file duplicate). Any database failure rolls the
    whole file back, so a retried import is safe to repeat.
    """
    rows = parse_csv(content)

    created = updated = 0
    for row in rows:
        params = _row_params(row)
        existing_id: str | None = None
        existing_stock: int | None = None

        if row.key_id:
            # D3: a valid product_id is THE canonical key — no name fallback
            # (products.id is TEXT; the value was validated as a UUID upstream)
            found = (
                await session.execute(
                    text("SELECT id, stock FROM public.products WHERE id = :k"),
                    {"k": row.key_id},
                )
            ).mappings().first()
            if found is not None:
                existing_id, existing_stock = str(found["id"]), int(found["stock"])
        else:
            found = (
                await session.execute(
                    text(
                        "SELECT id, stock FROM public.products "
                        "WHERE lower(regexp_replace(name, '\\s+', ' ', 'g')) = :n "
                        "AND lower(regexp_replace(category, '\\s+', ' ', 'g')) = :c "
                        "LIMIT 1"
                    ),
                    {"n": row.key_name, "c": row.key_category},
                )
            ).mappings().first()
            if found is not None:
                existing_id, existing_stock = str(found["id"]), int(found["stock"])

        if existing_id is None:
            # a new product needs the essentials
            for column in ("name", "category", "price"):
                if column not in params:
                    raise _fail(
                        row.no, f"محصول جدید به ستون «{column}» نیاز دارد"
                    )
            # `id` has no DB default: a name-keyed insert generates its own UUID
            insert_params: dict[str, Any] = {
                "id": row.key_id or str(uuid4()),
                **params,
            }
            columns = ["id", *[c for c in params if c != "is_new"]]
            values = [":id", *[_CASTS.get(c, f":{c}") for c in params if c != "is_new"]]
            if "is_new" in params:
                columns.append("is_new")
                values.append(":is_new")
            else:
                columns.append("is_new")
                values.append("true")
            new_id = (
                await session.execute(
                    text(
                        "INSERT INTO public.products "
                        f"({', '.join(columns)}) VALUES ({', '.join(values)}) "
                        "RETURNING id"
                    ),
                    insert_params,
                )
            ).scalar()
            pid = str(new_id)
            created += 1
        else:
            pid = existing_id
            if params:
                assignments = [
                    _CASTS.get(column, f"{column} = :{column}") for column in params
                ]
                await session.execute(
                    text(
                        "UPDATE public.products SET "
                        f"{', '.join(assignments)}, updated_at = now() "
                        "WHERE id = :pid"
                    ),
                    {**params, "pid": pid},
                )
                updated += 1

        # ledger rows follow the manual-edit rules (AB-BE-01): the opening stock
        # of a new product is a `restock`; a changed stock on an update is a
        # `manual_adjustment` delta. A zero delta writes nothing (the service's
        # own rule), so a re-import of an unchanged file stays idempotent.
        if existing_stock is None:
            if params.get("stock"):
                await log_stock_change(
                    session,
                    product_id=pid,
                    change=int(params["stock"]),
                    reason="restock",
                    actor_id=actor_id,
                )
        elif "stock" in params:
            await log_stock_change(
                session,
                product_id=pid,
                change=int(params["stock"]) - existing_stock,
                reason="manual_adjustment",
                actor_id=actor_id,
            )

    return {"created": created, "updated": updated, "total": len(rows)}
