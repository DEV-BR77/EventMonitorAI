import base64
from datetime import date
from pathlib import Path

from types import SimpleNamespace

from app.api.dashboard import statistics, update_person
from app.api.events import assign_event_person, list_events, update_assessment_exclusion
from app.api.push import noise_log
from app.core.config import settings
from app.database.base import Base
from app.models.dashboard import EventPersonAssignment, PersonProfile, User
from app.models.event import Event
from app.schemas.dashboard import PersonAssignmentWrite, PersonUpdate
from app.schemas.event import AssessmentExclusionUpdate
from app.services.person_media import store_photo
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_profile_photo_is_validated_and_stored(tmp_path: Path) -> None:
    original = settings.person_media_directory
    settings.person_media_directory = str(tmp_path)
    try:
        person = PersonProfile(id=7, name="Person 7")
        jpeg = b"\xff\xd8\xff" + b"test-image"
        path = store_photo(person, base64.b64encode(jpeg).decode(), "image/jpeg")
        assert path.read_bytes() == jpeg
        assert person.photo_path == str(path)
    finally:
        settings.person_media_directory = original


def test_person_can_be_excluded_from_noise_monitoring() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        person = PersonProfile(name="Nachbar", monitoring_enabled=True)
        event = Event(timestamp="2026-08-11T10:00:00", event_type="sound", label="Speech", label_de="Sprache", category="VOICE", confidence=0.8, db_level=55, device="mic")
        db.add_all([person, event])
        db.flush()
        db.add(EventPersonAssignment(event_id=event.id, person_id=person.id, confirmed=True))
        db.commit()

        update_person(person.id, PersonUpdate(name="Nachbar", active=True, monitoring_enabled=False), db, User(username="admin", password_hash="hash", role="admin"))
        db.refresh(event)
        assert event.person_monitoring_excluded is True

        update_person(person.id, PersonUpdate(name="Nachbar", active=True, monitoring_enabled=True), db, User(username="admin", password_hash="hash", role="admin"))
        db.refresh(event)
        assert event.person_monitoring_excluded is False


def test_live_event_person_assignment_is_returned_with_noise_exclusion() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        person = PersonProfile(name="Nachbar", monitoring_enabled=False)
        event = Event(timestamp="2026-08-11T10:00:00", event_type="sound", label="Speech", label_de="Sprache", category="VOICE", confidence=0.8, db_level=55, device="mic")
        db.add_all([person, event])
        db.commit()

        assign_event_person(
            event.id,
            PersonAssignmentWrite(person_id=person.id),
            db,
            User(username="operator", password_hash="hash", role="operator"),
        )

        listed = list_events(db, SimpleNamespace(), limit=10)
        logged = noise_log(db, SimpleNamespace(), limit=10)
        assert listed[0].person_id == person.id
        assert listed[0].person_monitoring_excluded is True
        assert logged[0].person_id == person.id
        assert logged[0].person_name == "Nachbar"
        assert logged[0].person_monitoring_excluded is True


def test_event_context_exclusion_keeps_raw_event_but_removes_statistics() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        event = Event(timestamp="2026-08-11T10:00:00", event_type="sound", label="Speech", label_de="Sprache", category="VOICE", confidence=0.8, db_level=55, device="mic")
        db.add(event)
        db.commit()

        result = update_assessment_exclusion(
            event.id,
            AssessmentExclusionUpdate(excluded=True, reason="near_field_conversation"),
            db,
            User(username="operator", password_hash="hash", role="operator"),
        )

        assert result.assessment_excluded is True
        assert result.assessment_exclusion_reason == "near_field_conversation"
        assert list_events(db, SimpleNamespace(), limit=10)[0].id == event.id
        assert statistics(
            db,
            SimpleNamespace(),
            date_from=date(2026, 8, 11),
            date_to=date(2026, 8, 11),
        )["total"] == 0
