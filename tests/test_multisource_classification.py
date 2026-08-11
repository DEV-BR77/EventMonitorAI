import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.events import bulk_classification, training_examples
from app.database.base import Base
from app.models.dashboard import AudioClip, EventClassificationRevision, Tenant, User
from app.models.event import Event, EventSecondaryClassification
from app.schemas.event import BulkClassificationUpdate
from app.services.taxonomy import seed_event_classes


def _event(label: str = "Clang and shouting") -> Event:
    return Event(timestamp="2026-08-11T21:00:00+02:00", event_type="sound", label=label, label_de=label, category="IMPACT", confidence=.8, db_level=67, device="mic")


def test_mixed_event_persists_secondary_source_without_implicit_learning() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        mixed, later = _event(), _event()
        db.add_all([user, mixed, later])
        db.commit()
        result = bulk_classification(BulkClassificationUpdate(event_ids=[mixed.id], primary_class_code="IMPACT", subclass_code="HIT_LAMPPOST", secondary_class_codes=["LOUD_CALLING"], secondary_learning_approved_codes=[], primary_learning_approved=False, reason="Metallschlag und gleichzeitiges Schreien"), db, user)

        assert result[0].secondary_class_codes == ["LOUD_CALLING"]
        assert result[0].primary_learning_approved is False
        assert result[0].secondary_learning_approved_codes == []
        assert later.classification_status == "automatic"
        revision = db.scalar(select(EventClassificationRevision))
        assert revision.secondary_class_codes == ["LOUD_CALLING"]
        assert revision.learning_approved_codes == []


def test_secondary_learning_requires_selected_secondary_class() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        event = _event()
        db.add_all([user, event])
        db.commit()
        with pytest.raises(HTTPException) as error:
            bulk_classification(BulkClassificationUpdate(event_ids=[event.id], primary_class_code="IMPACT", subclass_code="HIT_LAMPPOST", secondary_class_codes=[], secondary_learning_approved_codes=["LOUD_CALLING"], reason="Ungültige Lernfreigabe"), db, user)
        assert error.value.status_code == 422


def test_only_explicitly_approved_sources_are_exported_for_training() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        event = _event()
        db.add_all([user, event]); db.flush()
        db.add(AudioClip(device_id="mic", trigger_id="mixed", received_at=event.timestamp, sha256="a" * 64, path="mixed.wav", frame_count=16000, sample_rate=16000, event_id=event.id))
        db.commit()
        bulk_classification(BulkClassificationUpdate(event_ids=[event.id], primary_class_code="IMPACT", subclass_code="HIT_LAMPPOST", secondary_class_codes=["LOUD_CALLING"], secondary_learning_approved_codes=["LOUD_CALLING"], primary_learning_approved=False, reason="Nur die Nebenstimme ist sauber nutzbar"), db, user)
        examples = training_examples(db, user)
        assert [(item.assignment_role, item.subclass_code) for item in examples] == [("secondary", "LOUD_CALLING")]


def test_secondary_assignments_are_tenant_scoped() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, name="A", slug="a"), Tenant(id=2, name="B", slug="b")])
        db.flush()
        first, second = _event("A"), _event("B")
        first.tenant_id, second.tenant_id = 1, 2
        db.add_all([first, second]); db.flush()
        db.add_all([EventSecondaryClassification(tenant_id=1, event_id=first.id, class_code="LOUD_CALLING", learning_approved=False, assigned_by="a", assigned_at=first.timestamp), EventSecondaryClassification(tenant_id=2, event_id=second.id, class_code="ARGUMENT", learning_approved=False, assigned_by="b", assigned_at=second.timestamp)])
        db.commit()
        db.info["tenant_id"] = 1
        assert [item.class_code for item in db.scalars(select(EventSecondaryClassification))] == ["LOUD_CALLING"]


def test_frontend_keeps_secondary_controls_collapsed() -> None:
    javascript = open("frontend/app.js", encoding="utf-8").read()
    assert '<details class="secondary-editor">' in javascript
    assert "secondary_learning_approved_codes" in javascript
    assert "Gemischte Clips werden nur für ausdrücklich freigegebene Klassen gelernt" in javascript
