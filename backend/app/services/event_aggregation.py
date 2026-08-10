from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dashboard import AudioClip
from app.models.event import Event
from app.services.clips import normalized_utc

MAX_GAP_SECONDS = 4.0
VOICE_CATEGORIES = {"VOICE", "VOCALIZATION", "HUMAN_SOUND"}


def aggregation_key(event: Event) -> str:
    if event.primary_class_code:
        return event.primary_class_code
    if event.category in VOICE_CATEGORIES:
        return "VOICE_GROUP"
    return event.category or event.label.casefold().strip()


def event_end(event: Event):
    start = normalized_utc(event.timestamp)
    if event.end_timestamp:
        try:
            parsed_end = normalized_utc(event.end_timestamp)
            if parsed_end > start:
                return parsed_end
        except ValueError:
            pass
    return start + timedelta(seconds=max(0, event.duration_seconds))


def can_merge(previous: Event, current: Event) -> bool:
    if previous.device != current.device or aggregation_key(previous) != aggregation_key(current):
        return False
    if previous.classification_status == "manual" or current.classification_status == "manual":
        return False
    gap = (normalized_utc(current.timestamp) - event_end(previous)).total_seconds()
    return -1 <= gap <= MAX_GAP_SECONDS


def merge_into(previous: Event, current: Event) -> Event:
    previous_end = event_end(previous)
    current_end = event_end(current)
    combined_end = max(previous_end, current_end)
    previous.end_timestamp = combined_end.isoformat()
    previous.duration_seconds = round(
        max(0, (combined_end - normalized_utc(previous.timestamp)).total_seconds()), 3
    )
    previous.db_level = max(previous.db_level, current.db_level)
    previous.avg_db_level = round(
        ((previous.avg_db_level or previous.db_level) + (current.avg_db_level or current.db_level))
        / 2,
        2,
    )
    previous.confidence = max(previous.confidence, current.confidence)
    return previous


def merge_candidate(db: Session, current: Event) -> Event | None:
    candidates = list(
        db.scalars(
            select(Event)
            .where(Event.device == current.device, Event.classification_status != "manual")
            .order_by(Event.id.desc())
            .limit(20)
        )
    )
    for candidate in candidates:
        if can_merge(candidate, current):
            return merge_into(candidate, current)
    return None


def consolidate_existing_events(db: Session) -> int:
    events = list(
        db.scalars(
            select(Event)
            .where(Event.classification_status != "manual")
            .order_by(Event.device, Event.timestamp, Event.id)
        )
    )
    previous_by_device: dict[str, Event] = {}
    merged = 0
    for event in events:
        previous = previous_by_device.get(event.device)
        if previous is not None and can_merge(previous, event):
            merge_into(previous, event)
            previous_clip = db.scalars(
                select(AudioClip).where(AudioClip.event_id == previous.id)
            ).first()
            for clip in db.scalars(select(AudioClip).where(AudioClip.event_id == event.id)):
                clip.event_id = previous.id if previous_clip is None else None
                previous_clip = previous_clip or clip
            db.delete(event)
            merged += 1
        else:
            previous_by_device[event.device] = event
    db.commit()
    return merged
