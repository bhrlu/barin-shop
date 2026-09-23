"""Typed settings loaded from environment / .env file.

Owns everything now: database, auth (own JWTs), MinIO storage, payments.
There is no Supabase anymore.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str

    # Auth (own JWTs — HS256)
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # MinIO / S3 object storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "sande"
    minio_secret_key: str = "sande-secret"
    minio_bucket: str = "product-images"
    minio_secure: bool = False
    # Public base the browser uses for signed GET URLs (defaults to minio_endpoint)
    minio_public_endpoint: str = ""
    # Set explicitly so presigning never needs a GetBucketLocation round-trip
    # (the presign client points at the public host, which is not reachable
    # from inside the container). MinIO's default region is us-east-1.
    minio_region: str = "us-east-1"

    # Payment gateway (Zarinpal)
    zarinpal_merchant_id: str = "00000000-0000-0000-0000-000000000000"
    zarinpal_sandbox: bool = True

    # URLs
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # Shipping rules – mirror of the frontend cart logic (tomans)
    shipping_flat_fee: int = 89_000
    free_shipping_threshold: int = 2_000_000

    # Client IP (B5.1a audit + B3.11 throttle): comma-separated IPs/CIDRs of reverse
    # proxies whose X-Forwarded-For is believed. Empty = trust no proxy, use the
    # socket peer (compose publishes the backend directly, so XFF is client-set).
    trusted_proxies: str = ""

    # Contact-form abuse guard (B3.11, decision D1): attempts per IP per window
    contact_rate_limit: int = 5
    contact_rate_window_seconds: int = 600

    # Outbound notification providers (B2.1, decision D2). Environment only —
    # never the database. Empty = unconfigured: the channel sends nothing, and
    # internal notifications keep working.
    # SMS: Kavenegar (https://kavenegar.com)
    kavenegar_api_key: str = ""
    kavenegar_sender: str = ""  # dedicated line number; empty = account default
    # Email: plain SMTP (STARTTLS on 587 by default; SMTP_SSL=true for port 465)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    notification_provider_timeout_seconds: float = 10.0

    # Password reset (F2.3): link lifetime, and links per account per hour (the
    # cap stops mail-bombing an inbox; over it the API still answers the same way)
    password_reset_ttl_minutes: int = 30
    password_reset_max_per_hour: int = 3

    # Bootstrap admin (used by `python -m app.seed_auth`)
    admin_email: str = "admin@sande.local"
    admin_password: str = "admin1234"
    admin_full_name: str = "مدیر فروشگاه"

    @property
    def minio_public_host(self) -> str:
        return self.minio_public_endpoint or self.minio_endpoint


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
