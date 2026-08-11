from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser
from app.database.session import get_db
from app.models.dashboard import (
    AudioClip,
    EventPersonAssignment,
    EventWitnessResponse,
    PersonProfile,
    PushSubscription,
    User,
)
from app.models.event import Event
from app.schemas.dashboard import (
    NoiseLogEntry,
    PushConfigRead,
    PushSubscriptionWrite,
    WitnessResponseRead,
)
from app.services.push import decode_response_token

router = APIRouter(prefix="/push", tags=["Push notifications"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/config", response_model=PushConfigRead)
def push_config(_: CurrentUser) -> PushConfigRead:
    enabled = bool(settings.vapid_private_key and settings.vapid_public_key)
    return PushConfigRead(enabled=enabled, public_key=settings.vapid_public_key if enabled else "")


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(data: PushSubscriptionWrite, db: DatabaseSession, user: CurrentUser) -> None:
    subscription = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    )
    if subscription is None:
        subscription = PushSubscription(user_id=user.id, **data.model_dump())
        db.add(subscription)
    else:
        subscription.user_id = user.id
        subscription.p256dh = data.p256dh
        subscription.auth = data.auth
    db.commit()


@router.post("/respond", response_model=WitnessResponseRead)
def respond(
    token: str,
    response: Literal["confirmed", "rejected"],
    db: DatabaseSession,
) -> EventWitnessResponse:
    try:
        user_id, event_id = decode_response_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Ungültige oder abgelaufene Antwort") from exc
    user = db.get(User, user_id)
    event = db.get(Event, event_id)
    if user is None or not user.active or event is None:
        raise HTTPException(status_code=404, detail="Benutzer oder Ereignis nicht gefunden")
    witness = db.scalar(
        select(EventWitnessResponse).where(
            EventWitnessResponse.user_id == user_id,
            EventWitnessResponse.event_id == event_id,
        )
    )
    if witness is None:
        witness = EventWitnessResponse(
            user_id=user.id,
            event_id=event.id,
            username=user.username,
            response=response,
        )
        db.add(witness)
    else:
        witness.response = response
        witness.responded_at = datetime.now(UTC).isoformat()
    db.commit()
    db.refresh(witness)
    return witness


@router.get("/noise-log", response_model=list[NoiseLogEntry])
def noise_log(
    db: DatabaseSession,
    _: CurrentUser,
    limit: int = Query(default=100, ge=1, le=1000),
    start: str | None = None,
    end: str | None = None,
) -> list[NoiseLogEntry]:
    statement = select(Event).where(Event.display_suppressed.is_(False))
    if start:
        statement = statement.where(Event.timestamp >= start)
    if end:
        statement = statement.where(Event.timestamp < end)
    events = list(db.scalars(statement.order_by(desc(Event.id)).limit(limit)).all())
    if not events:
        return []
    event_ids = {event.id for event in events}
    audio_event_ids = set(
        db.scalars(select(AudioClip.event_id).where(AudioClip.event_id.in_(event_ids))).all()
    )
    assignments = {
        assignment.event_id: assignment.person_id
        for assignment in db.scalars(
            select(EventPersonAssignment).where(EventPersonAssignment.event_id.in_(event_ids))
        )
    }
    people = {
        person.id: person.name
        for person in db.scalars(
            select(PersonProfile).where(PersonProfile.id.in_(set(assignments.values())))
        )
    } if assignments else {}
    witnesses: dict[int, list[WitnessResponseRead]] = {event.id: [] for event in events}
    for item in db.scalars(
        select(EventWitnessResponse).where(EventWitnessResponse.event_id.in_(witnesses.keys()))
    ):
        witnesses[item.event_id].append(WitnessResponseRead.model_validate(item))
    return [
        NoiseLogEntry(
            event_id=event.id,
            timestamp=event.timestamp,
            end_timestamp=event.end_timestamp,
            duration_seconds=event.duration_seconds,
            device=event.device,
            label=event.label_de or event.label,
            primary_class_code=event.primary_class_code,
            subclass_code=event.subclass_code,
            classification_status=event.classification_status,
            corrected_by=event.corrected_by,
            db_level=event.db_level,
            audio_available=event.id in audio_event_ids,
            person_id=assignments.get(event.id),
            person_name=people.get(assignments.get(event.id)),
            person_monitoring_excluded=event.person_monitoring_excluded,
            witnesses=witnesses[event.id],
        )
        for event in events
    ]
