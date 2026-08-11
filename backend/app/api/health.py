from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["System"])


@router.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version, "service": settings.app_name}
