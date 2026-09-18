"""Storage endpoints backed by MinIO (S3-compatible).

Replaces Supabase Storage for the product-images bucket:
- POST /storage/upload-url  → presigned PUT URL the browser uploads to directly
- POST /storage/sign        → presigned GET URLs for stored references (uploads/…)

Image references that are bundled asset keys (e.g. "cat-tshirt") or absolute
URLs never hit this router — the frontend resolves those locally.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import AdminUser, CurrentUser
from app.config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/storage", tags=["storage"])


class UploadUrlIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(default="image/jpeg", max_length=100)


class UploadUrlOut(BaseModel):
    path: str
    upload_url: str
    public_url_template: str


class SignRequestIn(BaseModel):
    paths: list[str] = Field(max_length=100)


class SignedUrlOut(BaseModel):
    path: str
    url: str | None


def _client():
    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Object storage not configured"
        ) from exc
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@router.post("/upload-url", response_model=UploadUrlOut)
async def create_upload_url(body: UploadUrlIn, user: AdminUser) -> UploadUrlOut:
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp", "gif", "avif"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فرمت تصویر مجاز نیست")

    path = f"uploads/{uuid.uuid4()}.{ext}"
    client = _client()
    try:
        url = client.presigned_put_object(settings.minio_bucket, path, expires=3600)
    except Exception as exc:
        log.exception("presign failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در ساخت لینک آپلود") from exc

    public_base = f"{'https' if settings.minio_secure else 'http'}://{settings.minio_public_host}"
    return UploadUrlOut(
        path=path,
        upload_url=url,
        public_url_template=f"{public_base}/{settings.minio_bucket}",
    )


@router.post("/sign", response_model=list[SignedUrlOut])
async def sign_paths(body: SignRequestIn, user: CurrentUser) -> list[SignedUrlOut]:
    client = _client()
    out: list[SignedUrlOut] = []
    for path in body.paths:
        if not path.startswith("uploads/"):
            out.append(SignedUrlOut(path=path, url=None))
            continue
        try:
            url = client.presigned_get_object(settings.minio_bucket, path, expires=7 * 24 * 3600)
        except Exception:
            out.append(SignedUrlOut(path=path, url=None))
            continue
        out.append(SignedUrlOut(path=path, url=url))
    return out
