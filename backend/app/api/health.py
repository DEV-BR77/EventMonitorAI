from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.2.0-alpha",
        "service": "EventMonitorAI"
    }
