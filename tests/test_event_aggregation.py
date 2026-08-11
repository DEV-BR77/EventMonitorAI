from app.database.base import Base
from app.models.event import Event
from app.services.event_aggregation import can_merge, consolidate_existing_events, merge_into
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _event(timestamp: str, label: str = "Speech", category: str = "VOICE") -> Event:
    return Event(
        timestamp=timestamp,
        end_timestamp=timestamp,
        duration_seconds=0.975,
        event_type="sound",
        label=label,
        label_de=label,
        category=category,
        primary_class_code="VOICE_LOUD" if category == "VOICE" else None,
        confidence=0.8,
        db_level=60,
        avg_db_level=55,
        device="mic",
    )


def test_consecutive_voice_detections_form_one_timed_event() -> None:
    first = _event("2026-08-09T23:48:53+00:00")
    second = _event("2026-08-09T23:48:55+00:00", label="Shout")
    assert can_merge(first, second)
    merge_into(first, second)
    assert first.duration_seconds == 2.975
    assert first.end_timestamp.startswith("2026-08-09T23:48:55.975")


def test_existing_automatic_duplicates_are_consolidated() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                _event("2026-08-09T23:48:53+00:00"),
                _event("2026-08-09T23:48:55+00:00"),
                _event("2026-08-09T23:49:10+00:00"),
            ]
        )
        db.commit()
        assert consolidate_existing_events(db) == 1
        events = list(db.scalars(select(Event).order_by(Event.timestamp)))
        assert len(events) == 2
        assert events[0].duration_seconds == 2.975
