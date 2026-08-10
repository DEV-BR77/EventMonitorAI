import asyncio
from datetime import UTC, datetime

import pytest
from app.api.events import (
    _apply_learned_classifications,
    _contextual_class_for_detection,
    _learned_class_for_detection,
    correct_event_classification,
    event_classification_history,
)
from app.database.base import Base
from app.models.dashboard import EventClassificationRevision, User
from app.models.event import Event
from app.schemas.event import EventClassificationUpdate
from app.services.taxonomy import base_class_for_detection, seed_event_classes
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _event() -> Event:
    return Event(
        timestamp=datetime.now(UTC).isoformat(),
        event_type="AUDIO",
        label="Knock",
        label_de="Klopfen",
        category="IMPACT",
        confidence=0.91,
        db_level=67,
        device="mic",
        primary_class_code="IMPACT",
    )


def test_detection_maps_to_roadmap_base_classes() -> None:
    assert base_class_for_detection("Knock", "IMPACT") == "IMPACT"
    assert base_class_for_detection("Vehicle horn, car horn, honking", "VEHICLE") == "HORN"
    assert base_class_for_detection("Dog", "ANIMAL") == "DOG"


def test_manual_subclass_correction_is_audited() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        event = _event()
        db.add_all([user, event])
        db.commit()

        result = asyncio.run(
            correct_event_classification(
                event.id,
                EventClassificationUpdate(
                    primary_class_code="IMPACT",
                    subclass_code="BALL_METAL",
                    reason="Im Audioclip eindeutig bestätigt",
                ),
                db,
                user,
            )
        )

        assert result.classification_status == "manual"
        assert result.subclass_code == "BALL_METAL"
        assert result.corrected_by == "operator"
        revision = db.scalar(select(EventClassificationRevision))
        assert revision.reason == "Im Audioclip eindeutig bestätigt"
        assert event_classification_history(event.id, db, user)[0].actor == "operator"


def test_subclass_must_belong_to_selected_base_class() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        event = _event()
        db.add_all([user, event])
        db.commit()

        with pytest.raises(HTTPException) as error:
            asyncio.run(
                correct_event_classification(
                    event.id,
                    EventClassificationUpdate(
                        primary_class_code="VOICE_LOUD",
                        subclass_code="BALL_METAL",
                        reason="Falsche Kombination prüfen",
                    ),
                    db,
                    user,
                )
            )

        assert error.value.status_code == 422


def test_consistent_confirmations_are_learned_and_backfilled() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = _event()
        second = _event()
        pending = _event()
        for event in (first, second):
            event.label = "Cat"
            event.classification_status = "manual"
            event.primary_class_code = "VOICE_LOUD"
            event.subclass_code = "VOICE_SUSTAINED"
        pending.label = "Cat"
        pending.classification_status = "automatic"
        db.add_all([first, second, pending])
        db.flush()

        assert _learned_class_for_detection(db, "Cat") == (
            "VOICE_LOUD",
            "VOICE_SUSTAINED",
        )
        assert _apply_learned_classifications(db, second) == 1
        assert pending.classification_status == "learned"
        assert pending.subclass_code == "VOICE_SUSTAINED"


def test_conflicting_confirmations_do_not_create_a_rule() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for subclass in ("VOICE_SUSTAINED", "VOICE_SUSTAINED", "OTHER_NOISE"):
            event = _event()
            event.label = "Animal"
            event.classification_status = "manual"
            event.primary_class_code = "VOICE_LOUD" if subclass != "OTHER_NOISE" else "NO_NOISE"
            event.subclass_code = subclass
            db.add(event)
        db.flush()

        assert _learned_class_for_detection(db, "Animal") is None


def test_voice_context_bridges_different_detector_labels() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        reference = _event()
        reference.timestamp = "2026-08-10T20:00:00+00:00"
        reference.label = "Speech"
        reference.classification_status = "manual"
        reference.primary_class_code = "VOICE_LOUD"
        reference.subclass_code = "VOICE_SUSTAINED"
        db.add(reference)
        db.flush()

        assert _contextual_class_for_detection(
            db, "2026-08-10T20:00:08+00:00", "Cat", "ANIMAL"
        ) == ("VOICE_LOUD", "VOICE_SUSTAINED")
