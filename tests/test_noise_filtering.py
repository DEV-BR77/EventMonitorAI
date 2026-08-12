import asyncio
import json
from types import SimpleNamespace

from app.api.dashboard import statistics
from app.api.events import create_event, ignore_event_as_no_noise, list_events
from app.database.base import Base
from app.models.dashboard import AssessmentConfig, IgnoredDetectionPattern, User
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead
from app.services.taxonomy import seed_event_classes
from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _event(label: str = "Heartbeat") -> EventCreate:
    return EventCreate(
        timestamp="2026-08-09T04:00:00",
        label=label,
        confidence=0.8,
        db_level=54.0,
        device="mic",
    )


def test_wind_is_stored_for_learning_but_hidden_from_normal_views() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        event = asyncio.run(create_event(_event("Wind"), BackgroundTasks(), db, None))

        assert event.primary_class_code == "WIND"
        assert event.display_suppressed is True
        assert list_events(db, SimpleNamespace(), 100, None, None, None, None) == []
        assert statistics(db, SimpleNamespace(), 1)["total"] == 0


def test_three_no_noise_confirmations_discard_future_matching_detection() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        db.add(user)
        db.commit()
        for _ in range(3):
            event = asyncio.run(create_event(_event(), BackgroundTasks(), db, None))
            ignore_event_as_no_noise(event.id, db, user)

        pattern = db.scalar(select(IgnoredDetectionPattern))
        assert pattern is not None
        assert pattern.confirmations == 3
        assert list(db.scalars(select(Event))) == []

        discarded = asyncio.run(create_event(_event(), BackgroundTasks(), db, None))
        assert discarded.id == 0
        assert discarded.classification_status == "ignored"
        assert EventRead.model_validate(discarded).person_monitoring_excluded is False
        assert list(db.scalars(select(Event))) == []


def test_tenant_assessment_rules_filter_statistics_with_fine_override() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(AssessmentConfig(class_rules_json=json.dumps({"VEHICLE": False, "AIRCRAFT": True})))
        db.add_all(
            [
                Event(timestamp="2026-08-12T12:00:00+00:00", event_type="AUDIO", label="Car", label_de="Auto", category="VEHICLE", confidence=.9, db_level=70, device="mic", primary_class_code="VEHICLE"),
                Event(timestamp="2026-08-12T12:01:00+00:00", event_type="AUDIO", label="Aircraft", label_de="Flugzeug", category="VEHICLE", confidence=.9, db_level=75, device="mic", primary_class_code="VEHICLE", subclass_code="AIRCRAFT"),
            ]
        )
        db.commit()

        result = statistics(db, SimpleNamespace(), 1)

        assert result["total"] == 1
        assert result["max_db"] == 75
