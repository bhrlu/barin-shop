"""The API connects with a DML-only role; only the migrator runs DDL (B5.1e).

The backend used to connect as the schema owner — and, in the compose stack, as the
Postgres superuser — so any code path (or an injected query) could `ALTER`/`DROP` an
object, `SET session_replication_role` to bypass the append-only triggers (B5.1b /
AB-BE-01), or rewrite the audit trail. It now connects with a role that owns nothing
and may only read and write rows; `startup_ddl()` and the seeds (the compose `db-init`
job) keep the DDL as the schema owner.

Live-DB tests; they skip when no database is reachable. Every assertion below is a
statement the previous single-role setup allowed — that is the negative control.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.db import MigratorSessionLocal, SessionLocal, engine, migrator_engine, startup_ddl


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
async def db():
    await engine.dispose()
    if not await _db_available():
        pytest.skip("no database reachable — integration test skipped")
    if not settings.database_app_user:
        pytest.skip("no role split configured (DATABASE_APP_USER is empty)")
    await startup_ddl()
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


async def _refused(db, sql: str, *fragments: str) -> None:
    """The statement must fail, and for one of the named reasons (a syntax error or a
    missing object would otherwise pass for the wrong reason)."""
    with pytest.raises(DBAPIError) as exc:
        await db.execute(text(sql))
    message = str(exc.value)
    assert any(f in message for f in fragments), f"{sql!r} failed for the wrong reason: {message}"
    await db.rollback()


async def test_the_api_role_is_a_plain_dml_role(db):
    row = (
        await db.execute(
            text(
                "SELECT current_user AS name, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
                "       pg_get_userbyid(d.datdba) AS db_owner "
                "FROM pg_roles r, pg_database d "
                "WHERE r.rolname = current_user AND d.datname = current_database()"
            )
        )
    ).mappings().first()
    assert row["name"] == settings.database_app_user
    assert not row["rolsuper"], "the API role must not be a superuser"
    assert not row["rolcreatedb"] and not row["rolcreaterole"]
    assert row["db_owner"] != row["name"], "the API role must not own the database"
    owned = (
        await db.execute(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
                "WHERE r.rolname = current_user"
            )
        )
    ).scalar()
    assert owned == 0, f"the API role owns {owned} relation(s)"


async def test_the_api_role_cannot_run_ddl(db):
    await _refused(db, "CREATE TABLE public.b51e_nope (id int)", "permission denied")
    await _refused(
        db, "ALTER TABLE public.products ADD COLUMN b51e_nope INTEGER", "must be owner"
    )
    await _refused(db, "DROP TABLE public.products", "must be owner")
    await _refused(db, "TRUNCATE public.products", "permission denied")
    await _refused(
        db,
        "ALTER TABLE public.audit_logs DISABLE TRIGGER audit_logs_no_update_delete",
        "must be owner",
    )
    await _refused(
        db, "DROP TRIGGER audit_logs_no_update_delete ON public.audit_logs", "must be owner"
    )
    await _refused(db, "DROP INDEX public.product_variants_sku_key", "must be owner")
    await _refused(
        db,
        "CREATE INDEX b51e_nope_idx ON public.products(id)",
        "must be owner",
        "permission denied",
    )


async def test_the_api_role_cannot_bypass_the_append_only_triggers(db):
    """`session_replication_role` disables triggers entirely and needs a superuser."""
    await _refused(db, "SET session_replication_role = 'replica'", "permission denied")


async def test_the_api_role_can_do_everything_the_api_needs(db):
    """Rows access is complete: SELECT, INSERT, UPDATE, DELETE and sequence use."""
    pid = "b51e-scratch"
    try:
        await db.execute(
            text(
                "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
                "VALUES (:p, 'B51E scratch', 'test', 1000, ARRAY['M'], 3, true)"
            ),
            {"p": pid},
        )
        assert (
            await db.execute(
                text("SELECT stock FROM public.products WHERE id = :p"), {"p": pid}
            )
        ).scalar() == 3
        await db.execute(
            text("UPDATE public.products SET stock = 4 WHERE id = :p"), {"p": pid}
        )
        # a BIGSERIAL-backed table, i.e. the app role needs USAGE on sequences too
        seq = (
            await db.execute(
                text(
                    "INSERT INTO public.contact_attempts (ip, outcome) "
                    "VALUES ('b51e', 'accepted') RETURNING id"
                )
            )
        ).scalar()
        assert seq > 0
        await db.execute(text("DELETE FROM public.contact_attempts WHERE ip = 'b51e'"))
        await db.execute(text("DELETE FROM public.products WHERE id = :p"), {"p": pid})
        await db.commit()
        assert (
            await db.execute(
                text("SELECT count(*) FROM public.products WHERE id = :p"), {"p": pid}
            )
        ).scalar() == 0
    finally:
        await db.rollback()


async def test_the_migrator_is_a_different_role_that_owns_the_schema(db):
    """`startup_ddl()` keeps the DDL, as the owner — not as the role the API uses."""
    async with migrator_engine.connect() as conn:
        migrator = (await conn.execute(text("SELECT current_user"))).scalar()
    assert migrator != settings.database_app_user
    async with MigratorSessionLocal() as mig:
        owner = (
            await mig.execute(
                text(
                    "SELECT pg_get_userbyid(c.relowner) FROM pg_class c "
                    "WHERE c.oid = 'public.products'::regclass"
                )
            )
        ).scalar()
    assert owner == migrator
