from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0-alpha1",
        "service": "NoiseMonitorAI"
    }
