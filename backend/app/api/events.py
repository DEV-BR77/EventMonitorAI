from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser
from app.database.session import get_db
from app.models.dashboard import Device
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead
from app.services.label_translation import translate_label
from app.services.live import live_hub
from app.services.notifications import trigger_notifications

router = APIRouter(
    prefix="/events",
    tags=["Events"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def verify_ingest_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event_data: EventCreate,
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
