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


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)


class ResetPasswordRequest(BaseModel):
    # token_urlsafe(32) is 43 chars; the bound only keeps junk input small
    token: str = Field(min_length=20, max_length=200)
    # same policy as SignUpRequest
    password: str = Field(min_length=6, max_length=128)


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


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = Field(default=None, max_length=500)


class CartLine(BaseModel):
    product_id: str = Field(min_length=1)
    size: str = Field(min_length=1)
    color: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=20)


class CheckoutAddress(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=4, max_length=20)
    # optional so older payloads (and saved-address pre-fills) stay valid
    province: str | None = Field(default=None, max_length=80)
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
    # ceiling applied to a percent-off discount; None = uncapped (AB-BE-03)
    max_discount_cap: int | None = None


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off: int | None = Field(default=None, gt=0)
    min_subtotal: int = Field(default=0, ge=0)
    max_discount_cap: int | None = Field(default=None, gt=0)
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
    """Partial update: an omitted/null field is left unchanged (F5.16 clear rules).

    - `expires_at: ""` clears the expiry; `max_uses: 0` / `max_discount_cap: 0`
      clear the cap (back to unlimited / uncapped).
    - A coupon has exactly one kind: setting `percent_off` clears `amount_off`
      and vice versa (`compute_discount` prefers percent, so leaving both would
      silently ignore a switch to a fixed amount); sending both is a 422.
    """

    active: bool | None = None
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off: int | None = Field(default=None, gt=0)
    min_subtotal: int | None = Field(default=None, ge=0)
    # 0 clears the cap (back to uncapped); omitted leaves it unchanged, the same
    # convention `expires_at: ""` already uses on this schema (AB-BE-03)
    max_discount_cap: int | None = Field(default=None, ge=0)
    max_uses: int | None = Field(default=None, ge=0)
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
    """One rejected cart line.

    `reason` is a closed set shared with checkout's `stock_conflict` payload and
    with the frontend's message map, so the UI can explain every rejection:
      not_found           — product does not exist
      inactive            — product or its size×color variant is deactivated
      not_available       — `availability` is coming_soon / preorder
      size_invalid        — the size is not offered by this product
      insufficient_stock  — not enough units for the requested quantity
    """

    product_id: str
    reason: Literal[
        "not_found", "inactive", "not_available", "size_invalid", "insufficient_stock"
    ]
    available: int | None = None


class StockCheckOut(BaseModel):
    ok: bool
    subtotal: int
    issues: list[StockIssue]
    # F5.18: the server's unit price for each request line, in request order (variant
    # override or product price) so the storefront never prices a line itself; null
    # when the product does not exist
    unit_prices: list[int | None] = []


# --- products -------------------------------------------------------------------

class ProductColor(BaseModel):
    name: str
    hex: str


Availability = Literal["in_stock", "coming_soon", "preorder"]
Badge = Literal["sale", "coming_soon", "preorder", "new", "exclusive"]


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
    # merchandising / availability
    tags: list[str] = Field(default_factory=list)
    badge: Badge | None = None
    availability: Availability = "in_stock"
    available_at: str | None = None
    low_stock_threshold: int = Field(default=5, ge=0)


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
    tags: list[str] | None = None
    badge: Badge | None = None
    availability: Availability | None = None
    available_at: str | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)


class ProductOut(ProductBase):
    id: str
    created_at: str | None = None
    updated_at: str | None = None
    avg_rating: float | None = None
    review_count: int = 0


class ProductFacets(BaseModel):
    """Storefront filter options over the active catalogue (F5.8)."""

    sizes: list[str]
    colors: list[ProductColor]
    tags: list[str]
    price_min: int | None = None  # None when no product is active
    price_max: int | None = None


# --- product variants --------------------------------------------------------------


HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


def _strip_sku(value: str | None) -> str | None:
    """SKUs are unique when set (AB-BE-02); surrounding spaces are not part of one."""
    return value.strip() if isinstance(value, str) else value


class ProductVariantIn(BaseModel):
    size: str = Field(min_length=1, max_length=40)
    color: str = Field(min_length=1, max_length=60)
    sku: str | None = Field(default=None, max_length=80)
    stock: int = Field(default=0, ge=0)
    active: bool = True
    # AB-BE-02: NULL = the product's price; the only place a variant price comes from
    price_override: int | None = Field(default=None, gt=0)
    color_hex: str | None = Field(default=None, pattern=HEX_COLOR)

    @field_validator("sku")
    @classmethod
    def _blank_sku_is_none(cls, value: str | None) -> str | None:
        return _strip_sku(value) or None


class ProductVariantUpdateIn(BaseModel):
    """PATCH: omitted / null = unchanged. To clear (F5.16 convention): `sku: ""`,
    `price_override: 0`, `color_hex: ""`."""

    size: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = Field(default=None, min_length=1, max_length=60)
    sku: str | None = Field(default=None, max_length=80)
    stock: int | None = Field(default=None, ge=0)
    active: bool | None = None
    price_override: int | None = Field(default=None, ge=0)
    color_hex: str | None = Field(default=None, pattern=r"^(#[0-9a-fA-F]{6})?$")

    @field_validator("sku")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return _strip_sku(value)


class ProductVariantOut(BaseModel):
    id: UUID
    product_id: str
    size: str
    color: str
    sku: str | None
    stock: int
    active: bool
    price_override: int | None = None
    color_hex: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


# --- reviews & ratings --------------------------------------------------------------


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = Field(default="", max_length=120)
    body: str = Field(default="", max_length=2000)


class ReviewReplyIn(BaseModel):
    seller_reply: str = Field(min_length=1, max_length=2000)


class ReviewModerateIn(BaseModel):
    status: Literal["published", "hidden"]


class ReviewOut(BaseModel):
    id: UUID
    product_id: str
    user_id: UUID
    rating: int
    title: str
    body: str
    status: str
    seller_reply: str | None = None
    seller_replied_at: str | None = None
    created_at: str | None = None
    author_name: str | None = None


class ReviewListOut(BaseModel):
    product_id: str
    average: float | None
    count: int
    distribution: dict[int, int]
    reviews: list[ReviewOut]


# --- search history -----------------------------------------------------------------


class SearchSuggestion(BaseModel):
    id: str | None
    label: str
    kind: Literal["product", "category", "tag", "query"]
    image: str | None = None


class SearchHistoryOut(BaseModel):
    id: UUID
    query: str
    created_at: str | None = None


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


class AddressUpdateIn(BaseModel):
    """Partial address edit; every field is optional.

    `is_default` is honoured with a single-default guarantee: setting it true
    clears the flag on the caller's other addresses (`routers/addresses.py`).
    """

    title: str | None = Field(default=None, min_length=1, max_length=40)
    receiver: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=4, max_length=20)
    province: str | None = Field(default=None, min_length=2, max_length=80)
    city: str | None = Field(default=None, min_length=2, max_length=80)
    postal_code: str | None = None
    line: str | None = Field(default=None, min_length=5, max_length=500)
    is_default: bool | None = None


class AddressOut(AddressIn):
    id: UUID
    created_at: str | None = None


# --- contact ----------------------------------------------------------------------

class ContactMessageIn(BaseModel):
    """Public contact form. `contact` is whatever the sender left us — an email
    address or a phone number — so no format is enforced beyond a sane length."""

    name: str = Field(min_length=2, max_length=120)
    contact: str = Field(min_length=5, max_length=120)
    message: str = Field(min_length=5, max_length=2000)
    # B3.11 honeypot: the form renders this off-screen, so only bots fill it.
    # Kept free of any description — the OpenAPI schema is public.
    website: str | None = Field(default=None, max_length=200)


class ContactMessageStatusIn(BaseModel):
    """Admin inbox update — only these two states exist today."""

    status: Literal["new", "answered"]


class ContactMessageOut(BaseModel):
    id: UUID
    user_id: UUID | None = None
    name: str
    contact: str
    message: str
    status: str
    created_at: str | None = None


# --- favorites ----------------------------------------------------------------------

class FavoriteToggleOut(BaseModel):
    product_id: str
    is_favorite: bool
