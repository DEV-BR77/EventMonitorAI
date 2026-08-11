import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.api.dashboard import create_event_class
from app.database.base import Base
from app.models.dashboard import EventClass
from app.models.event import Event
from app.schemas.dashboard import EventClassWrite
from app.services.taxonomy import DEFAULT_EVENT_CLASSES, seed_event_classes
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.insert(0, str(AUDIO_LAB_DIR))

from eventmonitor.db import connect  # noqa: E402
from eventmonitor.taxonomy import active_class_names, sync_class_definitions  # noqa: E402


def test_backend_seeds_two_level_roadmap_taxonomy() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        classes = list(db.scalars(select(EventClass).order_by(EventClass.sort_order)))

        assert len(classes) == len(DEFAULT_EVENT_CLASSES)
        assert {item.level for item in classes} == {"base", "fine"}
        assert next(item for item in classes if item.code == "BALL_METAL").parent_code == "IMPACT"
        assert (
            next(item for item in classes if item.code == "IMPACT").name == "Schlag/Aufprall/Knall"
        )
        assert next(item for item in classes if item.code == "FIRECRACKER").parent_code == "IMPACT"
        assert (
            next(item for item in classes if item.code == "LOUD_CALLING").parent_code
            == "VOICE_LOUD"
        )
        assert not next(item for item in classes if item.code == "LOUD_SCREAM").active
        assert not next(item for item in classes if item.code == "VOICE_SUSTAINED").active
        assert next(item for item in classes if item.code == "ARGUMENT").parent_code == "VOICE_LOUD"
        assert next(item for item in classes if item.code == "TRAIN_HORN").parent_code == "HORN"

        legacy_event = Event(
            timestamp="2026-08-10T20:00:00+00:00",
            event_type="AUDIO",
            label="Speech",
            label_de="Sprache",
            category="VOICE",
            confidence=0.9,
            db_level=60,
            device="mic",
            primary_class_code="VOICE_LOUD",
            subclass_code="VOICE_SUSTAINED",
            classification_status="manual",
        )
        db.add(legacy_event)
        db.commit()
        seed_event_classes(db)
        assert legacy_event.subclass_code == "LOUD_CALLING"


def test_dashboard_rejects_fine_class_with_unknown_parent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, pytest.raises(HTTPException) as error:
        create_event_class(
            EventClassWrite(
                code="CUSTOM_FINE",
                name="Eigene Feinzuordnung",
                level="fine",
                parent_code="MISSING",
            ),
            db,
            SimpleNamespace(role="admin"),
        )

    assert error.value.status_code == 422


def test_audiolab_synchronizes_dashboard_taxonomy(tmp_path: Path) -> None:
    conn = connect(tmp_path / "taxonomy.sqlite3")
    definitions = [
        {
            "code": "IMPACT",
            "name": "Schlag/Aufprall",
            "level": "base",
            "parent_code": None,
            "active": True,
            "trainable": True,
            "sort_order": 1,
        },
        {
            "code": "BALL_WOOD",
            "name": "Fußball gegen Holz",
            "level": "fine",
            "parent_code": "IMPACT",
            "active": True,
            "trainable": True,
            "sort_order": 2,
        },
    ]

    assert sync_class_definitions(conn, definitions) == 2
    assert active_class_names(conn) == ["Schlag/Aufprall", "Fußball gegen Holz"]
    assert conn.execute("SELECT COUNT(*) FROM event_classes WHERE active=0").fetchone()[0] > 0
