from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, require_roles
from app.database.session import get_db
from app.models.dashboard import (
    AudioClip,
    Device,
    DeviceLevelSample,
    DeviceTelemetry,
    EventClass,
    EventClassificationRevision,
    ReviewRun,
    User,
)
from app.models.event import Event
from app.schemas.dashboard import DeviceTelemetryRead, DeviceTelemetryWrite
from app.schemas.event import (
    BulkClassificationUpdate,
    EventClassificationRevisionRead,
    EventClassificationUpdate,
    EventCreate,
    EventRead,
    ReviewQueueItem,
    ReviewRunCreate,
    ReviewRunRead,
    ReviewSummary,
    TrainingExampleRead,
)
from app.services.audio import live_audio_hub
from app.services.clips import associate_nearest_clip, associate_nearest_event, store_training_clip
from app.services.label_translation import translate_label
from app.services.live import live_hub
from app.services.noise_assessment import assessment_for
from app.services.notifications import trigger_notifications
from app.services.push import send_event_pushes
from app.services.review import process_review_run
from app.services.taxonomy import base_class_for_detection

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

    previous_sample = db.scalar(
        select(DeviceLevelSample)
        .where(DeviceLevelSample.device_id == data.device_id)
        .order_by(desc(DeviceLevelSample.id))
        .limit(1)
    )
    if (
        previous_sample is None
        or (
            datetime.fromisoformat(now) - datetime.fromisoformat(previous_sample.timestamp)
        ).total_seconds()
        >= 5
    ):
        db.add(
            DeviceLevelSample(
                device_id=data.device_id,
                timestamp=now,
                db_level=data.db_level,
            )
        )
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        db.execute(delete(DeviceLevelSample).where(DeviceLevelSample.timestamp < cutoff))

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
        primary_class_code=base_class_for_detection(event_data.label, category),
        classification_status="automatic",
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    associate_nearest_clip(db, event)
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


@router.post("/clips/{device_id}", status_code=status.HTTP_201_CREATED)
def ingest_training_clip(
    device_id: str,
    payload: Annotated[bytes, Body(media_type="audio/wav")],
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
    x_trigger_id: Annotated[str, Header(max_length=64)],
    x_trigger_uptime_ms: Annotated[int, Header(ge=0)],
    x_received_at: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise HTTPException(status_code=404, detail="Unknown device")
    try:
        clip = store_training_clip(
            db,
            payload,
            device_id=device_id,
            trigger_id=x_trigger_id,
            trigger_uptime_ms=x_trigger_uptime_ms,
            received_at=x_received_at or datetime.now(UTC).isoformat(),
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    associate_nearest_event(db, clip)
    db.commit()
    return {"clip_id": clip.id, "sha256": clip.sha256, "event_id": clip.event_id}


@router.get("/training-examples", response_model=list[TrainingExampleRead])
def training_examples(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[TrainingExampleRead]:
    rows = db.execute(
        select(Event, AudioClip, EventClass)
        .join(AudioClip, AudioClip.event_id == Event.id)
        .join(EventClass, EventClass.code == Event.subclass_code)
        .where(
            Event.classification_status == "manual",
            Event.primary_class_code.is_not(None),
            Event.subclass_code.is_not(None),
        )
        .order_by(Event.id)
    ).all()
    return [
        TrainingExampleRead(
            event_id=event.id,
            device_id=clip.device_id,
            timestamp=event.timestamp,
            primary_class_code=event.primary_class_code,
            subclass_code=event.subclass_code,
            label=event_class.name,
            confidence=event.confidence,
            clip_sha256=clip.sha256,
            audio_url=f"/events/training-examples/{event.id}/audio",
        )
        for event, clip, event_class in rows
    ]


@router.get("/training-examples/{event_id}/audio")
def training_example_audio(
    event_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> FileResponse:
    clip = db.scalar(select(AudioClip).where(AudioClip.event_id == event_id))
    event = db.get(Event, event_id)
    if (
        clip is None
        or event is None
        or event.classification_status != "manual"
        or event.subclass_code is None
    ):
        raise HTTPException(status_code=404, detail="Trainingsbeispiel nicht gefunden")
    return FileResponse(clip.path, media_type="audio/wav", filename=f"event-{event_id}.wav")


def _validate_classes(
    db: Session, primary_code: str, subclass_code: str | None
) -> tuple[EventClass, EventClass | None]:
    primary = db.scalar(select(EventClass).where(EventClass.code == primary_code))
    if primary is None or primary.level != "base" or not primary.active:
        raise HTTPException(status_code=422, detail="Ungültige oder inaktive Basisklasse")
    subclass = None
    if subclass_code:
        subclass = db.scalar(select(EventClass).where(EventClass.code == subclass_code))
        if (
            subclass is None
            or subclass.level != "fine"
            or not subclass.active
            or subclass.parent_code not in (None, primary.code)
        ):
            raise HTTPException(status_code=422, detail="Feinzuordnung passt nicht zur Basisklasse")
    return primary, subclass


def _assign_manual(
    event: Event, primary: EventClass, subclass: EventClass | None, user: User, reason: str
) -> None:
    now = datetime.now(UTC).isoformat()
    event.primary_class_code = primary.code
    event.subclass_code = subclass.code if subclass else None
    event.classification_status = "manual"
    event.corrected_by = user.username
    event.corrected_at = now


@router.get("/review/summary", response_model=ReviewSummary)
def review_summary(db: DatabaseSession, _: CurrentUser) -> ReviewSummary:
    events = list(db.scalars(select(Event)))
    summary = {
        "open_unknown": 0,
        "open_recognized": 0,
        "completed_unknown": 0,
        "completed_recognized": 0,
    }
    by_class: dict[str, dict[str, int]] = {}
    for event in events:
        completed = event.classification_status == "manual"
        recognized = event.primary_class_code is not None
        summary[
            f"{'completed' if completed else 'open'}_{'recognized' if recognized else 'unknown'}"
        ] += 1
        code = event.subclass_code or event.primary_class_code or "UNKNOWN"
        counts = by_class.setdefault(code, {"open": 0, "completed": 0})
        counts["completed" if completed else "open"] += 1
    return ReviewSummary(**summary, by_class=by_class)


@router.get("/review/queue", response_model=list[ReviewQueueItem])
def review_queue(
    db: DatabaseSession,
    _: CurrentUser,
    class_code: str | None = None,
    status_filter: str = Query(default="open", alias="status", pattern="^(open|completed|all)$"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[Event]:
    statement = select(Event)
    if status_filter == "open":
        statement = statement.where(Event.classification_status != "manual")
    elif status_filter == "completed":
        statement = statement.where(Event.classification_status == "manual")
    if class_code == "UNKNOWN":
        statement = statement.where(Event.primary_class_code.is_(None))
    elif class_code:
        statement = statement.where(
            (Event.primary_class_code == class_code) | (Event.subclass_code == class_code)
        )
    return list(db.scalars(statement.order_by(desc(Event.id)).limit(limit)))


@router.post("/review/bulk-classification", response_model=list[EventRead])
def bulk_classification(
    data: BulkClassificationUpdate,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[Event]:
    primary, subclass = _validate_classes(db, data.primary_class_code, data.subclass_code)
    events = list(db.scalars(select(Event).where(Event.id.in_(set(data.event_ids)))))
    if len(events) != len(set(data.event_ids)):
        raise HTTPException(status_code=404, detail="Mindestens ein Ereignis wurde nicht gefunden")
    for event in events:
        _assign_manual(event, primary, subclass, user, data.reason)
        db.add(
            EventClassificationRevision(
                event_id=event.id,
                primary_class_code=primary.code,
                subclass_code=event.subclass_code,
                status="manual",
                actor=user.username,
                reason=data.reason,
                created_at=event.corrected_at,
            )
        )
    db.commit()
    return events


@router.get("/review/runs", response_model=list[ReviewRunRead])
def review_runs(db: DatabaseSession, _: CurrentUser) -> list[ReviewRun]:
    return list(db.scalars(select(ReviewRun).order_by(desc(ReviewRun.id)).limit(20)))


@router.post("/review/runs", response_model=ReviewRunRead, status_code=201)
def start_review_run(
    data: ReviewRunCreate,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    active = db.scalar(select(ReviewRun).where(ReviewRun.status.in_(("pending", "running"))))
    if active:
        raise HTTPException(status_code=409, detail="Es läuft bereits ein Prüflauf")
    run = ReviewRun(kind=data.kind, status="pending", requested_by=user.username)
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(process_review_run, run.id)
    return run


@router.post("/review/runs/{run_id}/pause", response_model=ReviewRunRead)
def pause_review_run(
    run_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    run = db.get(ReviewRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Prüflauf nicht gefunden")
    if run.status in {"pending", "running"}:
        run.status = "paused"
        run.message = "Prüflauf manuell unterbrochen."
        db.commit()
    return run


@router.post("/review/runs/{run_id}/resume", response_model=ReviewRunRead)
def resume_review_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    run = db.get(ReviewRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Prüflauf nicht gefunden")
    if run.status != "paused":
        raise HTTPException(
            status_code=409, detail="Nur unterbrochene Prüfläufe können fortgesetzt werden"
        )
    run.status = "pending"
    run.message = ""
    db.commit()
    background_tasks.add_task(process_review_run, run.id)
    return run


@router.get("/{event_id}/assessment")
def event_assessment(event_id: int, db: DatabaseSession, _: CurrentUser) -> dict[str, object]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    return assessment_for(event.timestamp, event.db_level)


@router.patch("/{event_id}/classification", response_model=EventRead)
async def correct_event_classification(
    event_id: int,
    data: EventClassificationUpdate,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    primary, subclass = _validate_classes(db, data.primary_class_code, data.subclass_code)
    _assign_manual(event, primary, subclass, user, data.reason)
    db.add(
        EventClassificationRevision(
            event_id=event.id,
            primary_class_code=primary.code,
            subclass_code=event.subclass_code,
            status="manual",
            actor=user.username,
            reason=data.reason,
            created_at=event.corrected_at,
        )
    )
    db.commit()
    db.refresh(event)
    await live_hub.broadcast(EventRead.model_validate(event).model_dump())
    return event


@router.get(
    "/{event_id}/classification-history",
    response_model=list[EventClassificationRevisionRead],
)
def event_classification_history(
    event_id: int,
    db: DatabaseSession,
    _: CurrentUser,
) -> list[EventClassificationRevision]:
    if db.get(Event, event_id) is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    return list(
        db.scalars(
            select(EventClassificationRevision)
            .where(EventClassificationRevision.event_id == event_id)
            .order_by(EventClassificationRevision.id)
        )
    )


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
