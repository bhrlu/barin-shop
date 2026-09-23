"""Test-session defaults (B6.13) and the least-privilege role bootstrap (B5.1e).

`app.config.settings` is built once, at the first `import app…`, and cached. The
test modules used to set `DATABASE_URL` themselves at import time; the first one
collected (`test_addresses.py`) set a dummy URL, so every live-DB module then
skipped as "no database reachable" and the documented `pytest -q` looked green
while running none of the integration tests.

pytest imports this file before any test module, so the one default lives here:
the local docker-compose Postgres. An exported `DATABASE_URL` still wins
(`setdefault`), and the live-DB tests still skip when nothing answers on it.

B5.1e: `DATABASE_URL` is the **DML-only application role** the API connects with,
and `DATABASE_MIGRATOR_URL` the schema owner that runs `startup_ddl()` — the same
split the compose stack has, so the suite exercises the API under the role it
really runs as. The bootstrap below creates that role before the first test
connects as it; each live-DB module then runs `startup_ddl()` (owner) itself, as
the seeds do.
"""

import asyncio
import os
import sys

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://sande_app:sande-app@localhost:5432/postgres"
)
os.environ.setdefault(
    "DATABASE_MIGRATOR_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres"
)
os.environ.setdefault("DATABASE_APP_USER", "sande_app")
os.environ.setdefault("DATABASE_APP_PASSWORD", "sande-app")
os.environ.setdefault("JWT_SECRET", "test-secret")


def _bootstrap_app_role() -> None:
    """Create/refresh the DML-only application role once, at collection time.

    Uses a throwaway engine disposed inside the same event loop, so no pooled
    connection outlives it (the module engines stay untouched). A missing database
    — or an owner that cannot create roles — is not fatal: the live-DB modules
    skip on their own, and this says so once instead of looking green in silence.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.db import app_role_ddl

    if not settings.database_app_user:
        return
    url = settings.database_migrator_url or settings.database_url
    statements = app_role_ddl(settings.database_app_user, settings.database_app_password)

    async def run() -> None:
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                for statement in statements:
                    await conn.execute(text(statement))
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    except Exception as exc:  # noqa: BLE001 — no database / no permission to split roles
        print(f"[conftest] app-role bootstrap skipped: {exc!r}", file=sys.stderr)


_bootstrap_app_role()
