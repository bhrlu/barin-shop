"""Async SQLAlchemy engine/session and idempotent startup DDL for the coupon tables.

The app connects directly to the Supabase Postgres database (service role = bypasses RLS).
Existing Supabase tables (products, orders, ...) are modelled in app/models.py but are
NOT created by this app; only the coupon tables are auto-created idempotently on startup.
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
# The coupon tables are the one part of the schema the API owns itself; the rest
# comes from the migrations. Created on startup so a fresh database works with no
# manual step. Kept idempotent because `seed_coupons` runs this too, and the
# compose db-init job can run before the API has ever booted.
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


async def startup_ddl() -> None:
    async with engine.begin() as conn:
        for stmt in COUPON_DDL:
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
