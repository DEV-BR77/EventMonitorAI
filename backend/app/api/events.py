from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead
from app.services.label_translation import translate_label

router = APIRouter(
    prefix="/events",
    tags=["Events"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: EventCreate,
    db: DatabaseSession,
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

    return event


@router.get(
    "",
    response_model=list[EventRead],
)
def list_events(
    db: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[Event]:
    statement = select(Event).order_by(desc(Event.id)).limit(limit)

    return list(db.scalars(statement).all())
