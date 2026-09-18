"""Health check."""

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "sandeh-backend", "version": __version__}
