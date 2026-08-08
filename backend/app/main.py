from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.push import router as push_router
from app.core.config import settings
from app.core.security import decode_token
from app.database.init_db import init_db
from app.database.session import engine
from app.models.dashboard import Device, LiveAudioAccess, User
from app.services.audio import live_audio_hub
from app.services.live import live_hub


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered local sound monitoring platform",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(dashboard_router)
app.include_router(push_router)


@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket, token: str) -> None:
    decode_token(token)
    await live_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        live_hub.disconnect(websocket)


@app.websocket("/ws/audio/{device_id}")
async def audio_stream(websocket: WebSocket, device_id: str, token: str) -> None:
    try:
        payload = decode_token(token)
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.username == payload["sub"]))
            device = db.scalar(select(Device).where(Device.device_id == device_id))
            allowed = bool(
                user
                and user.active
                and device
                and device.enabled
                and (
                    user.role == "admin"
                    or db.scalar(
                        select(LiveAudioAccess.id).where(
                            LiveAudioAccess.user_id == user.id,
                            LiveAudioAccess.device_id == device_id,
                        )
                    )
                )
            )
        if not allowed:
            await websocket.close(code=4403)
            return
    except Exception:
        await websocket.close(code=4401)
        return

    await live_audio_hub.connect(device_id, websocket, settings.audio_sample_rate)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        live_audio_hub.disconnect(device_id, websocket)


frontend = Path(__file__).resolve().parents[2] / "frontend"
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="dashboard")
