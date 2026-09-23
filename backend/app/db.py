"""Async SQLAlchemy engine/session and the idempotent startup DDL.

The app connects straight to the Postgres instance described by `DATABASE_URL`
with a role that owns the schema (there is no Supabase and no RLS any more).
Base tables (products, orders, ...) come from `infra/initdb/`; this module owns
only the **additive** tables and columns the API needs on top of them, created
idempotently on startup so a fresh database and an already-seeded one converge
with no manual migration step.
"""

import re
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def co_purchase_ddl() -> str:
    from app.services.recommendations import co_purchase_ddl as _ddl

    return _ddl()

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
    # ceiling (in tomans) for a percent-off coupon on a large cart (AB-BE-03 /
    # spec [BE-02]). NULL = uncapped, which is what every existing coupon keeps.
    # Fixed `amount_off` coupons ignore it — their discount is already a ceiling.
    (
        "ALTER TABLE public.coupons ADD COLUMN IF NOT EXISTS max_discount_cap INTEGER "
        "CHECK (max_discount_cap IS NULL OR max_discount_cap > 0)"
    ),
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
    # which variant an order line took its stock from (B6.8). NULL on legacy
    # rows and on products without a variant matrix — cancellation then only
    # restores the product aggregate. ON DELETE SET NULL so removing a variant
    # never deletes order history.
    (
        "ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS variant_id UUID "
        "REFERENCES public.product_variants(id) ON DELETE SET NULL"
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


# --- Refund settlement fields (idempotent) -----------------------------------
# Spec [BE-03]: the approval flow records HOW the money was sent and WHO/WHEN it
# was resolved. `bank_tracking_code` is the Paya/Satna tracking code entered at
# settlement ([FE-06] requires it when marking a request `refunded`).
#
# Vocabulary: the base DDL (infra/initdb) defaults `status` to 'requested' while
# the API and UI speak pending/approved/rejected/refunded. New rows are inserted
# with 'pending' explicitly, and the UPDATE below normalizes any legacy
# 'requested' rows — without touching rows that already hold a settlement state.
REFUND_DDL = [
    "ALTER TABLE public.refund_requests ADD COLUMN IF NOT EXISTS bank_tracking_code TEXT",
    (
        "ALTER TABLE public.refund_requests ADD COLUMN IF NOT EXISTS resolved_by "
        "UUID REFERENCES public.users(id) ON DELETE SET NULL"
    ),
    "ALTER TABLE public.refund_requests ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ",
    (
        "UPDATE public.refund_requests SET status = 'pending' "
        "WHERE status = 'requested'"
    ),
]


# --- Granular staff roles (idempotent) ---------------------------------------
# Spec [BE-04] / B5.4: extends the role enum in place. Roles stay in
# `user_roles` (never on the user row). `ADD VALUE` cannot run inside a
# transaction on older Postgres, so these run on an AUTOCOMMIT connection.
# Legacy 'admin' rows keep working — the API treats 'admin' as a full-equivalent
# staff role (Rule 4: existing rows never break).
ROLE_DDL = [
    "ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'super_admin'",
    "ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'order_manager'",
    "ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'support'",
]


# --- Admin audit log (idempotent) --------------------------------------------
# Spec [BE-04] / B5.1: tamper-resistant trail of privileged mutations. Written by
# `app/services/audit.py` on the same session as the mutation it describes, so
# the entry commits atomically with it. `ip_address` stays NULL until request
# client IPs are plumbed through.
AUDIT_DDL = [
    """
    CREATE TABLE IF NOT EXISTS public.audit_logs (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      admin_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      old_values JSONB,
      new_values JSONB,
      ip_address TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS audit_logs_created_idx "
        "ON public.audit_logs(created_at DESC)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS audit_logs_entity_idx "
        "ON public.audit_logs(entity_type, entity_id)"
    ),
    # B5.1b: append-only. The app's DB role owns the table (and is a superuser in
    # the compose stack), so REVOKE cannot enforce it — triggers do. The one change
    # allowed is the FK's ON DELETE SET NULL when a user is deleted: attribution is
    # lost, nothing else may move. (A superuser can still disable triggers — full
    # proof needs a least-privilege app role, B5.1e.)
    """
    CREATE OR REPLACE FUNCTION public.audit_logs_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'UPDATE' AND OLD.admin_id IS NOT NULL AND NEW.admin_id IS NULL
         AND (NEW.id, NEW.action, NEW.entity_type, NEW.entity_id, NEW.old_values,
              NEW.new_values, NEW.ip_address, NEW.created_at)
             IS NOT DISTINCT FROM
             (OLD.id, OLD.action, OLD.entity_type, OLD.entity_id, OLD.old_values,
              OLD.new_values, OLD.ip_address, OLD.created_at) THEN
        RETURN NEW;
      END IF;
      RAISE EXCEPTION 'audit_logs is append-only (% refused)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
    END $$
    """,
    (
        "CREATE TRIGGER audit_logs_no_update_delete BEFORE UPDATE OR DELETE "
        "ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION public.audit_logs_append_only()"
    ),
    (
        "CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE "
        "ON public.audit_logs FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.audit_logs_append_only()"
    ),
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
    # B3.11: one row per POST /contact attempt (accepted or rejected) — the
    # per-IP sliding window of decision D1; pruned after a day by the guard
    """
    CREATE TABLE IF NOT EXISTS public.contact_attempts (
      id BIGSERIAL PRIMARY KEY,
      ip TEXT NOT NULL,
      outcome TEXT NOT NULL CHECK (outcome IN ('accepted', 'honeypot', 'throttled')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS contact_attempts_ip_created_idx "
        "ON public.contact_attempts(ip, created_at DESC)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS contact_attempts_created_idx "
        "ON public.contact_attempts(created_at)"
    ),
]


# --- Notifications (idempotent) ----------------------------------------------
# B2.1 / decision D2. `notifications` is the in-app inbox: one row per user per
# business event, written by `app/services/notifications.py` on the same session
# as the event, so it commits or rolls back with it. UNIQUE (user_id, event_key)
# is the single dedup mechanism — a repeated transition (`order:<id>:paid`, …)
# inserts nothing. Unread = `read_at IS NULL`.
#
# `notification_deliveries` is the outbox for the external channels (SMS/email):
# a row is written only when the admin switched the channel on, and is sent
# after the commit. UNIQUE (notification_id, channel) means one message per
# channel per event. `notification_settings` is a single row (id = true) holding
# the admin switches; provider credentials never live in the database.
NOTIFICATION_DDL = [
    """
    CREATE TABLE IF NOT EXISTS public.notifications (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      type TEXT NOT NULL,
      title TEXT NOT NULL,
      message TEXT NOT NULL,
      data JSONB NOT NULL DEFAULT '{}'::jsonb,
      event_key TEXT NOT NULL,
      read_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (user_id, event_key)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS notifications_user_created_idx "
        "ON public.notifications(user_id, created_at DESC)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS notifications_user_unread_idx "
        "ON public.notifications(user_id) WHERE read_at IS NULL"
    ),
    """
    CREATE TABLE IF NOT EXISTS public.notification_deliveries (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      notification_id UUID NOT NULL REFERENCES public.notifications(id) ON DELETE CASCADE,
      channel TEXT NOT NULL CHECK (channel IN ('sms', 'email')),
      recipient TEXT,
      status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
      provider TEXT,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (notification_id, channel)
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS notification_deliveries_open_idx "
        "ON public.notification_deliveries(created_at) "
        "WHERE status IN ('pending', 'failed')"
    ),
    """
    CREATE TABLE IF NOT EXISTS public.notification_settings (
      id BOOLEAN PRIMARY KEY DEFAULT true CHECK (id),
      sms_enabled BOOLEAN NOT NULL DEFAULT false,
      email_enabled BOOLEAN NOT NULL DEFAULT false,
      updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "INSERT INTO public.notification_settings (id) VALUES (true) ON CONFLICT (id) DO NOTHING",
]


# --- Password reset tokens (idempotent) --------------------------------------
# F2.3. Only the SHA-256 of the emailed token is stored, so a database reader
# cannot use a pending link. A row is spent by setting `used_at` (on reset, or
# when a newer link supersedes it); rows older than a day are pruned on request.
PASSWORD_RESET_DDL = [
    """
    CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      token_hash TEXT NOT NULL UNIQUE,
      expires_at TIMESTAMPTZ NOT NULL,
      used_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS password_reset_tokens_user_idx "
        "ON public.password_reset_tokens(user_id, created_at DESC)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS password_reset_tokens_created_idx "
        "ON public.password_reset_tokens(created_at)"
    ),
    # B6.14: tokens issued before this moment are dead (checked in app/auth.py).
    # NULL on every existing row = no cutoff, so no current session is affected.
    "ALTER TABLE public.users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ",
]


# --- Lock-free steady-state boot (B6.16) --------------------------------------
# `IF NOT EXISTS` does not make DDL cheap: `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
# takes an ACCESS EXCLUSIVE lock on the table even when the column is there, and
# `CREATE INDEX IF NOT EXISTS` a SHARE lock. Run on every boot (and by every seed
# job), that blocked — and could deadlock with — requests in flight during a
# restart. Each guarded statement is now checked against the catalog first and
# only runs when its object is missing; statements this cannot recognise (the
# backfill UPDATEs, the settings-row INSERT — row locks only) still always run.
_DDL_GUARDS = [
    (
        re.compile(
            r"ALTER\s+TABLE\s+public\.(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)",
            re.I,
        ),
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :a AND column_name = :b)",
    ),
    (
        re.compile(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)", re.I),
        "SELECT to_regclass('public.' || :a) IS NULL",
    ),
    (
        re.compile(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\.(\w+)", re.I),
        "SELECT to_regclass('public.' || :a) IS NULL",
    ),
    # functions are created once; changing a body later means a new function name
    (
        re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\.(\w+)", re.I),
        "SELECT to_regproc('public.' || :a) IS NULL",
    ),
    (
        re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)\s.*?\sON\s+public\.(\w+)",
            re.I | re.S,
        ),
        "SELECT NOT EXISTS (SELECT 1 FROM pg_trigger "
        "WHERE tgname = :a AND tgrelid = to_regclass('public.' || :b))",
    ),
    (
        re.compile(
            r"ALTER\s+TYPE\s+public\.(\w+)\s+ADD\s+VALUE\s+IF\s+NOT\s+EXISTS\s+'([^']+)'",
            re.I,
        ),
        "SELECT NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = :a AND e.enumlabel = :b)",
    ),
]


async def ddl_needed(conn, stmt: str) -> bool:
    """False when the object a guarded DDL statement would create already exists."""
    for pattern, check in _DDL_GUARDS:
        match = pattern.match(stmt.strip())
        if match:
            params = {"a": match.group(1)}
            if match.lastindex and match.lastindex >= 2:
                params["b"] = match.group(2)
            return bool((await conn.execute(text(check), params)).scalar())
    return True


async def startup_ddl() -> None:
    # enum extension first, on its own autocommit connection (ADD VALUE and
    # older Postgres transactions do not mix)
    conn = await engine.connect()
    try:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        for stmt in ROLE_DDL:
            if await ddl_needed(conn, stmt):
                await conn.execute(text(stmt))
    finally:
        await conn.close()

    async with engine.begin() as conn:
        # one process at a time (backend boot, the seed jobs, tests) — taken before
        # the timeout below, so waiting for another boot's DDL is not bounded
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('ddl', 0))"))
        # a DDL that is really needed waits at most this long for its table lock
        # instead of queueing every request behind it
        await conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        for statements in (
            COUPON_DDL,
            CATALOG_DDL,
            TRACKING_DDL,
            REFUND_DDL,
            AUDIT_DDL,
            PAYMENT_DDL,
            CONTACT_DDL,
            NOTIFICATION_DDL,
            PASSWORD_RESET_DDL,
            [co_purchase_ddl()],
        ):
            for stmt in statements:
                if await ddl_needed(conn, stmt):
                    await conn.execute(text(stmt))

    # first co-purchase refresh so /recommendations has data on fresh stacks
    from app.services.recommendations import refresh_co_purchases

    async with SessionLocal() as session:
        try:
            await refresh_co_purchases(session)
            await session.commit()
        except Exception:
            pass  # fresh DB without seed data; refreshed again after each checkout


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction-scoped session per request."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
