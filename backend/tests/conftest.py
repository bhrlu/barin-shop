"""Test-session defaults (B6.13).

`app.config.settings` is built once, at the first `import app…`, and cached. The
test modules used to set `DATABASE_URL` themselves at import time; the first one
collected (`test_addresses.py`) set a dummy URL, so every live-DB module then
skipped as "no database reachable" and the documented `pytest -q` looked green
while running none of the integration tests.

pytest imports this file before any test module, so the one default lives here:
the local docker-compose Postgres. An exported `DATABASE_URL` still wins
(`setdefault`), and the live-DB tests still skip when nothing answers on it.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres"
)
os.environ.setdefault("JWT_SECRET", "test-secret")
