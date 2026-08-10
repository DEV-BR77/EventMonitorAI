import base64
from pathlib import Path

from app.api.dashboard import update_person
from app.core.config import settings
from app.database.base import Base
from app.models.dashboard import EventPersonAssignment, PersonProfile, User
from app.models.event import Event
from app.schemas.dashboard import PersonUpdate
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
