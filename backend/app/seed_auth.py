"""Seed a bootstrap admin + demo customer.

Run from backend/:
    python -m app.seed_auth

Requires DATABASE_URL + JWT_SECRET (and ADMIN_EMAIL/ADMIN_PASSWORD to override
the defaults). Idempotent.
"""

import asyncio

from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.security import hash_password


async def seed_user(email: str, password: str, full_name: str, role: str) -> None:
    async with engine.begin() as conn:
        email_norm = email.strip().lower()
        existing = (
            await conn.execute(
                text("SELECT id FROM public.users WHERE lower(email) = :email"),
                {"email": email_norm},
            )
        ).first()
        if existing is not None:
            print(f"  • {email_norm} already exists")
            return

        uid = (
            await conn.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:email, :hash) RETURNING id"
                ),
                {"email": email_norm, "hash": hash_password(password)},
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO public.profiles (id, full_name) VALUES (:uid, :name)"),
            {"uid": str(uid), "name": full_name},
        )
        await conn.execute(
            text("INSERT INTO public.user_roles (user_id, role) VALUES (:uid, :role)"),
            {"uid": str(uid), "role": role},
        )
        print(f"  ✓ {email_norm} ({role})")


async def main() -> None:
    print("seeding auth users…")
    await seed_user(
        settings.admin_email, settings.admin_password, settings.admin_full_name, "admin"
    )
    await seed_user("customer@sande.local", "customer1234", "مشتری نمونه", "customer")
    # granular staff roles (B5.4) — demo accounts for the capability matrix
    await seed_user("ordermgr@sande.local", "staff1234", "مدیر سفارش‌ها", "order_manager")
    await seed_user("support@sande.local", "staff1234", "پشتیبانی", "support")
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
