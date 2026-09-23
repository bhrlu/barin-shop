"""Storage endpoints backed by MinIO (S3-compatible) — the product-images bucket
the store uses instead of the former Supabase Storage:
- POST /storage/upload-url  → presigned POST policy the browser uploads with directly
- POST /storage/sign        → presigned GET URLs for stored references (uploads/…)

Image references that are bundled asset keys (e.g. "cat-tshirt") or absolute
URLs never hit this router — the frontend resolves those locally.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import urllib3
from fastapi import APIRouter, HTTPException, status
from minio.datatypes import PostPolicy
from minio.error import MinioException
from pydantic import BaseModel, Field

from app.auth import CurrentUser, StaffCatalog
from app.config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/storage", tags=["storage"])

# B6.18: the gallery's «≤ 5 MB, image/*» rule used to be client-side only — a
# presigned PUT signs no length and no content type, so anyone holding an upload
# URL could store an object of any size and type. A POST policy carries both
# limits inside the signed policy, so MinIO itself refuses the upload.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}


class UploadUrlIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(default="image/jpeg", max_length=100)


class UploadUrlOut(BaseModel):
    path: str
    # the bucket URL the multipart POST goes to
    upload_url: str
    # policy-signed form fields; the client appends every one, then `file` last
    fields: dict[str, str]
    # the ceiling the policy enforces (bytes)
    max_bytes: int


class SignRequestIn(BaseModel):
    paths: list[str] = Field(max_length=100)


class SignedUrlOut(BaseModel):
    path: str
    url: str | None


def _client():
    """Client used only to presign URLs.

    Presigning is pure local signing with no network call, so it points at the
    browser-reachable host rather than the in-cluster one. The host is part of
    what gets signed, so signing for `minio:9000` while the browser sends
    `localhost:9000` would be rejected with SignatureDoesNotMatch.
    """
    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Object storage not configured"
        ) from exc
    return Minio(
        settings.minio_public_host,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )


# what MinIO / the network may raise; anything else is a bug and must surface as a
# 500 instead of a 502 or a silent `url: null` (B6.9a — the `expires` int bug noted
# below used to hide behind the broad `except Exception`)
_STORAGE_ERRORS = (MinioException, urllib3.exceptions.HTTPError, OSError)


# B6.17: whoever may edit the catalog may add product images — `AdminUser` meant
# admin/super_admin only and refused order_manager, who edits products since B5.4b
@router.post("/upload-url", response_model=UploadUrlOut)
async def create_upload_url(body: UploadUrlIn, user: StaffCatalog) -> UploadUrlOut:
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else "jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فرمت تصویر مجاز نیست")
    if not body.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "فرمت تصویر مجاز نیست")

    path = f"uploads/{uuid.uuid4()}.{ext}"
    client = _client()
    try:
        # minio-py requires a datetime here — the policy expires with the link.
        # Signing happens locally, like the former PUT presign: the region is set
        # on the client, so no GetBucketLocation round-trip is needed.
        policy = PostPolicy(settings.minio_bucket, datetime.now(UTC) + timedelta(hours=1))
        # the object key, the size ceiling and an image content type are all part
        # of the signature — MinIO rejects a form that does not honour them
        policy.add_equals_condition("key", path)
        policy.add_content_length_range_condition(1, MAX_IMAGE_BYTES)
        policy.add_starts_with_condition("Content-Type", "image/")
        fields = client.presigned_post_policy(policy)
    except _STORAGE_ERRORS as exc:
        log.exception("presign failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در ساخت لینک آپلود") from exc

    # minio-py signs the policy but leaves `key` out of the form; MinIO compares a
    # `Content-Type` form field against the condition, not the file part's header
    fields["key"] = path
    fields["Content-Type"] = body.content_type

    public_base = f"{'https' if settings.minio_secure else 'http'}://{settings.minio_public_host}"
    return UploadUrlOut(
        path=path,
        upload_url=f"{public_base}/{settings.minio_bucket}",
        fields=fields,
        max_bytes=MAX_IMAGE_BYTES,
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
            url = client.presigned_get_object(
                settings.minio_bucket, path, expires=timedelta(days=7)
            )
        except _STORAGE_ERRORS:
            log.warning("signing %s failed", path, exc_info=True)
            out.append(SignedUrlOut(path=path, url=None))
            continue
        out.append(SignedUrlOut(path=path, url=url))
    return out
