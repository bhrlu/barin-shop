"""Seed two starter coupons (idempotent): the real SANDE10 and a welcome coupon.

Run from backend/:
    python -m app.seed_coupons
Requires DATABASE_URL only.

The coupon tables are created by the API at startup, which has not necessarily
happened yet when seeding (the compose db-init job runs first), so this script
runs the same idempotent DDL itself.
"""

import asyncio

from sqlalchemy import text

from app.db import engine, startup_ddl


async def main() -> None:
    await startup_ddl()
    stmts = [
        text(
            "INSERT INTO public.coupons (code, percent_off, min_subtotal, max_uses_per_user) "
            "VALUES ('SANDE10', 10, 0, 1) ON CONFLICT (code) DO NOTHING"
        ),
        text(
            "INSERT INTO public.coupons (code, amount_off, min_subtotal, max_uses_per_user) "
            "VALUES ('WELCOME500', 50000, 500000, 1) ON CONFLICT (code) DO NOTHING"
        ),
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(stmt)
    print("seeded: SANDE10 (10%), WELCOME500 (50,000 تومان off over 500,000)")


if __name__ == "__main__":
    asyncio.run(main())
