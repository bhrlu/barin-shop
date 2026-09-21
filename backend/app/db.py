"""Async SQLAlchemy engine/session and the idempotent startup DDL.

The app connects straight to the Postgres instance described by `DATABASE_URL`
with a role that owns the schema (there is no Supabase and no RLS any more).
Base tables (products, orders, ...) come from `infra/initdb/`; this module owns
only the **additive** tables and columns the API needs on top of them, created
idempotently on startup so a fresh database and an already-seeded one converge
with no manual migration step.
"""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


# --- Coupon tables DDL (idempotent) -----------------------------------------
# Coupons were the first part of the schema the API owned itself. Created on
# startup so a fresh database works with no manual step. Kept idempotent because
# `seed_coupons` runs this too, and the compose db-init job can run before the API
# has ever booted.
COUPON_DDL = [
    """
    CREATE TABLE IF NOT EXISTS public.coupons (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      code TEXT NOT NULL UNIQUE,
      percent_off INTEGER CHECK (percent_off IS NULL OR percent_off BETWEEN 1 AND 100),
      amount_off INTEGER CHECK (amount_off IS NULL OR amount_off > 0),
      min_subtotal INTEGER NOT NULL DEFAULT 0,
      max_uses INTEGER,               -- total redemption cap (NULL = unlimited)
      max_uses_per_user INTEGER NOT NULL DEFAULT 1,
      used_count INTEGER NOT NULL DEFAULT 0,
      starts_at TIMESTAMPTZ,
      expires_at TIMESTAMPTZ,
      active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.coupon_redemptions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      coupon_id UUID NOT NULL REFERENCES public.coupons(id) ON DELETE CASCADE,
      order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      amount INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (coupon_id, order_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS coupon_redemptions_user_idx ON public.coupon_redemptions(user_id)",
]


# --- Catalog DDL (idempotent) ------------------------------------------------
# Product-catalog features the API owns on top of the base `products` table:
# merchandising columns, per-variant stock, reviews, search history and
# recently-viewed. Kept idempotent so a fresh database and an already-seeded one
# both converge with no manual migration step.
CATALOG_DDL = [
    # merchandising / availability columns on products
    "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}'",
    "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS badge TEXT",
    (
        "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS availability TEXT "
        "NOT NULL DEFAULT 'in_stock'"
    ),
    "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ",
    (
        "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER "
        "NOT NULL DEFAULT 5"
    ),
    # per-variant (size × color) stock
    """
    CREATE TABLE IF NOT EXISTS public.product_variants (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      product_id TEXT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
      size TEXT NOT NULL,
      color TEXT NOT NULL,
      sku TEXT,
      stock INTEGER NOT NULL DEFAULT 0,
      active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (product_id, size, color)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS product_variants_product_idx "
        "ON public.product_variants(product_id)"
    ),
    # reviews + ratings (+ seller reply)
    """
    CREATE TABLE IF NOT EXISTS public.product_reviews (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      product_id TEXT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
      title TEXT NOT NULL DEFAULT '',
      body TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'published',
      seller_reply TEXT,
      seller_replied_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (product_id, user_id)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS product_reviews_product_idx "
        "ON public.product_reviews(product_id, created_at DESC)"
    ),
    # search history (autocomplete recency)
    """
    CREATE TABLE IF NOT EXISTS public.search_history (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      query TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS search_history_user_idx "
        "ON public.search_history(user_id, created_at DESC)"
    ),
    # recently viewed
    """
    CREATE TABLE IF NOT EXISTS public.recently_viewed (
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      product_id TEXT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
      viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (user_id, product_id)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS recently_viewed_user_idx "
        "ON public.recently_viewed(user_id, viewed_at DESC)"
    ),
]


# --- Payments DDL (idempotent) -----------------------------------------------
# `payments.reference` used to double as the gateway authority while a session was
# pending and then be overwritten with the `SND-…` code on success, which made a
# repeat callback unfindable (it looked the row up by authority). The authority
# now has its own column, and a one-off backfill copies it out of `reference` for
# the rows created before that.
# --- Order shipment tracking (idempotent) ------------------------------------
# Admin-entered postal / courier tracking code (Iran Post / Tipax, F2.8). NULL
# until an admin sets it; shown on the customer's order page once present.
TRACKING_DDL = [
    "ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS tracking_code TEXT",
]


PAYMENT_DDL = [
    "ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS authority TEXT",
    (
        "UPDATE public.payments SET authority = reference "
        "WHERE authority IS NULL AND status = 'pending' AND reference IS NOT NULL"
    ),
    "CREATE INDEX IF NOT EXISTS payments_authority_idx ON public.payments(authority)",
]


# --- Contact messages (idempotent) -------------------------------------------
# The public contact form used to be display-only. `user_id` stays NULL for a
# guest submission; `contact` holds whatever the sender left (email or phone).
CONTACT_DDL = [
    """
    CREATE TABLE IF NOT EXISTS public.contact_messages (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
      name TEXT NOT NULL,
      contact TEXT NOT NULL,
      message TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'new',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS contact_messages_created_idx "
        "ON public.contact_messages(created_at DESC)"
    ),
]


async def startup_ddl() -> None:
    async with engine.begin() as conn:
        for statements in (
            COUPON_DDL,
            CATALOG_DDL,
            TRACKING_DDL,
            PAYMENT_DDL,
            CONTACT_DDL,
        ):
            for stmt in statements:
                await conn.execute(text(stmt))


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction-scoped session per request."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
