from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser
from app.database.session import get_db
from app.models.dashboard import Device, DeviceTelemetry
from app.models.event import Event
from app.schemas.dashboard import DeviceTelemetryRead, DeviceTelemetryWrite
from app.schemas.event import EventCreate, EventRead
from app.services.audio import live_audio_hub
from app.services.label_translation import translate_label
from app.services.live import live_hub
from app.services.notifications import trigger_notifications
from app.services.push import send_event_pushes

router = APIRouter(
    prefix="/events",
    tags=["Events"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def verify_ingest_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.post("/audio/{device_id}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_live_audio(
    device_id: str,
    pcm: Annotated[bytes, Body(media_type="application/octet-stream")],
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> dict[str, int]:
    if not pcm or len(pcm) > 64_000 or len(pcm) % 2:
        raise HTTPException(status_code=422, detail="Invalid 16-bit PCM chunk")
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Unknown device")
    if not device.enabled:
        raise HTTPException(status_code=409, detail="Device disabled")
    listeners = await live_audio_hub.broadcast(device_id, pcm)
    return {"bytes": len(pcm), "listeners": listeners}


@router.post("/telemetry", response_model=DeviceTelemetryRead)
def update_device_telemetry(
    data: DeviceTelemetryWrite,
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> DeviceTelemetry:
    now = datetime.now(UTC).isoformat()
    telemetry = db.scalar(
        select(DeviceTelemetry).where(DeviceTelemetry.device_id == data.device_id)
    )
    values = data.model_dump()
    total = values["packets_received"] + values["packets_lost"]
    values["loss_rate"] = round(values["packets_lost"] / total, 6) if total else 0.0
    values["last_seen"] = now
    if telemetry is None:
        telemetry = DeviceTelemetry(**values)
        db.add(telemetry)
    else:
        for key, value in values.items():
            setattr(telemetry, key, value)

    device = db.scalar(select(Device).where(Device.device_id == data.device_id))
    if device is None:
        db.add(Device(device_id=data.device_id, name=data.device_id, last_seen=now))
    else:
        device.last_seen = now
    db.commit()
    db.refresh(telemetry)
    return telemetry


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event_data: EventCreate,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> Event:
    label_de, category = translate_label(
        event_data.label,
        event_data.device,
    )

    event_values = event_data.model_dump()

    if event_values["end_timestamp"] is None:
        event_values["end_timestamp"] = event_values["timestamp"]

    if event_values["avg_db_level"] is None:
        event_values["avg_db_level"] = event_values["db_level"]

    event = Event(
        **event_values,
        label_de=label_de,
        category=category,
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    device = db.scalar(select(Device).where(Device.device_id == event.device))
    if device is None:
        db.add(Device(device_id=event.device, name=event.device, last_seen=event.timestamp))
    else:
        device.last_seen = event.timestamp
    db.commit()
    await live_hub.broadcast(EventRead.model_validate(event).model_dump())
    trigger_notifications(db, event)
    background_tasks.add_task(send_event_pushes, event.id)

    return event


@router.get(
    "",
    response_model=list[EventRead],
)
def list_events(
    db: DatabaseSession,
    _: CurrentUser,
    limit: int = Query(default=100, ge=1, le=1000),
    device: str | None = None,
    category: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[Event]:
    statement = select(Event)
    if device:
        statement = statement.where(Event.device == device)
    if category:
        statement = statement.where(Event.category == category)
    if start:
        statement = statement.where(Event.timestamp >= start)
    if end:
        statement = statement.where(Event.timestamp <= end)
    statement = statement.order_by(desc(Event.id)).limit(limit)

    return list(db.scalars(statement).all())
