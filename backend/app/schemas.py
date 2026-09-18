"""Pydantic request/response schemas shared by the routers."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

CartLineIn = tuple[str, str, str, int]  # productId, size, color, quantity


class AuthUser(BaseModel):
    """Shape of the backend's JWT subject, shared by auth dependencies."""

    user_id: UUID
    email: str | None = None
    role: str = "customer"


class SignUpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class SignInRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: "UserInfoOut"


class UserInfoOut(BaseModel):
    id: UUID
    email: str | None
    full_name: str | None
    phone: str | None
    avatar_url: str | None
    role: str
    created_at: str | None = None


class CartLine(BaseModel):
    product_id: str = Field(min_length=1)
    size: str = Field(min_length=1)
    color: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=20)


class CheckoutAddress(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=4, max_length=20)
    city: str = Field(min_length=2, max_length=80)
    line: str = Field(min_length=5, max_length=500)
    postal_code: str | None = None
    note: str | None = None


class CheckoutRequest(BaseModel):
    lines: list[CartLine] = Field(min_length=1)
    address: CheckoutAddress
    coupon_code: str | None = None


class CouponValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    subtotal: int = Field(ge=0)


class CouponOut(BaseModel):
    code: str
    discount: int
    percent_off: int | None
    amount_off: int | None
    min_subtotal: int
    expires_at: str | None


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off: int | None = Field(default=None, gt=0)
    min_subtotal: int = Field(default=0, ge=0)
    max_uses: int | None = Field(default=None, gt=0)
    max_uses_per_user: int = Field(default=1, ge=1)
    expires_at: str | None = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return None if v in ("", None) else v

    @field_validator("percent_off", "amount_off")
    @classmethod
    def _not_both(cls, v: Any, info: Any) -> Any:
        return v


class CouponUpdate(BaseModel):
    active: bool | None = None
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off: int | None = Field(default=None, gt=0)
    min_subtotal: int | None = Field(default=None, ge=0)
    max_uses: int | None = Field(default=None, gt=0)
    max_uses_per_user: int | None = Field(default=None, ge=1)
    expires_at: str | None = None


class PaymentRequest(BaseModel):
    order_id: UUID
    method: Literal["zarinpal"] = "zarinpal"


class PaymentStartOut(BaseModel):
    authority: str
    redirect_url: str
    amount: int


class PaymentVerifyOut(BaseModel):
    status: Literal["paid", "failed", "already_paid"]
    reference: str | None
    amount: int


class SearchHit(BaseModel):
    id: str
    name: str
    category: str
    price: int
    old_price: int | None
    image: str | None
    stock: int
    is_new: bool


class SearchOut(BaseModel):
    query: str
    total: int
    hits: list[SearchHit]


class OrderCreated(BaseModel):
    order_id: UUID
    order_number: str
    subtotal: int
    discount: int
    shipping: int
    total: int
    coupon_applied: str | None


class StockCheckLine(BaseModel):
    product_id: str
    size: str
    color: str
    quantity: int = Field(ge=1, le=20)


class StockCheckRequest(BaseModel):
    lines: list[StockCheckLine] = Field(min_length=1)


class StockIssue(BaseModel):
    product_id: str
    reason: Literal["not_found", "inactive", "insufficient_stock"]
    available: int | None = None


class StockCheckOut(BaseModel):
    ok: bool
    subtotal: int
    issues: list[StockIssue]


# --- products -------------------------------------------------------------------

class ProductColor(BaseModel):
    name: str
    hex: str


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=40)
    price: int = Field(gt=0)
    old_price: int | None = Field(default=None, gt=0)
    sizes: list[str] = Field(default_factory=list)
    colors: list[ProductColor] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    material: str = ""
    description: str = ""
    is_new: bool = True
    stock: int = Field(default=0, ge=0)
    active: bool = True


class ProductIn(ProductBase):
    pass


class ProductUpdateIn(BaseModel):
    name: str | None = None
    category: str | None = None
    price: int | None = Field(default=None, gt=0)
    old_price: int | None = Field(default=None, gt=0)
    sizes: list[str] | None = None
    colors: list[ProductColor] | None = None
    images: list[str] | None = None
    material: str | None = None
    description: str | None = None
    is_new: bool | None = None
    stock: int | None = Field(default=None, ge=0)
    active: bool | None = None


class ProductOut(ProductBase):
    id: str
    created_at: str | None = None
    updated_at: str | None = None


# --- addresses --------------------------------------------------------------------

class AddressIn(BaseModel):
    title: str = "خانه"
    receiver: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=4, max_length=20)
    province: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    postal_code: str | None = None
    line: str = Field(min_length=5, max_length=500)
    is_default: bool = False


class AddressOut(AddressIn):
    id: UUID
    created_at: str | None = None


# --- favorites ----------------------------------------------------------------------

class FavoriteToggleOut(BaseModel):
    product_id: str
    is_favorite: bool
