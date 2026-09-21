"""SQLAlchemy models for the base schema (products, orders, users, …).

Only the columns this backend actually reads/writes are declared. Constraints
(FKs, uniques, defaults) already live in the database — the base schema comes from
`infra/initdb/` and the API only adds its own tables/columns through the idempotent
DDL lists in `app/db.py` — so no ForeignKey declarations are needed here.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- products -----------------------------------------------------------------
class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer)
    old_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sizes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    colors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    images: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    material: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # merchandising / availability (added by the idempotent catalog DDL)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    badge: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability: Mapped[str] = mapped_column(Text, default="in_stock")
    available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- catalog extensions: variants / reviews / history --------------------------
class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_id: Mapped[str] = mapped_column(String)
    size: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductReview(Base):
    __tablename__ = "product_reviews"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    product_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="published")
    seller_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(Uuid)
    query: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecentlyViewed(Base):
    __tablename__ = "recently_viewed"

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- orders / order items / payments ------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_number: Mapped[str] = mapped_column(Text, unique=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(Text, default="pending")
    payment_status: Mapped[str] = mapped_column(Text, default="unpaid")
    payment_method: Mapped[str] = mapped_column(Text, default="online")
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    shipping: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # admin-entered postal/courier tracking code (F2.8); NULL until set
    tracking_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[UUID] = mapped_column(Uuid)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer)
    size: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(Text, default="online")
    status: Mapped[str] = mapped_column(Text, default="pending")
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- coupons (new tables, created by startup DDL) -------------------------------
class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(Text, unique=True)
    percent_off: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_off: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_subtotal: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses_per_user: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    coupon_id: Mapped[UUID] = mapped_column(Uuid)
    order_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[Decimal] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- refunds (columns added by REFUND_DDL; table itself from infra/initdb) ------
class RefundRequest(Base):
    """Mirrors `public.refund_requests` for reference; the routers speak raw SQL
    for this table. `status`: pending / approved / rejected / refunded (the
    startup DDL normalizes legacy 'requested' rows to 'pending')."""

    __tablename__ = "refund_requests"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_tracking_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
