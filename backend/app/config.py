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

    # Payment gateway (Zarinpal)
    zarinpal_merchant_id: str = "00000000-0000-0000-0000-000000000000"
    zarinpal_sandbox: bool = True

    # URLs
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # Shipping rules – mirror of the frontend cart logic (tomans)
    shipping_flat_fee: int = 89_000
    free_shipping_threshold: int = 2_000_000

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
