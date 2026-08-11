import app.services.review as review_service
from app.api.events import bulk_classification, review_queue, review_summary
from app.database.base import Base
from app.models.dashboard import EventClassificationRevision, ReviewRun, User
from app.models.event import Event
from app.schemas.event import BulkClassificationUpdate
from app.services.noise_assessment import assessment_for
from app.services.taxonomy import seed_event_classes
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def event(label: str, primary: str | None = None) -> Event:
    return Event(
        timestamp="2026-08-08T20:30:00+02:00",
        event_type="AUDIO",
        label=label,
        label_de=label,
        category="OTHER",
        confidence=0.8,
        db_level=32,
        device="mic",
        primary_class_code=primary,
        classification_status="automatic",
    )


def test_bulk_review_summary_and_class_filter() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_event_classes(db)
        user = User(username="operator", password_hash="x", role="operator")
        unknown = event("Unknown")
        impact = event("Knock", "IMPACT")
        db.add_all([user, unknown, impact])
        db.commit()

        before = review_summary(db, user)
        assert before.open_unknown == 1
        assert before.open_recognized == 1
        assert [item.id for item in review_queue(db, user, "UNKNOWN", "open", 20)] == [unknown.id]

        results = bulk_classification(
            BulkClassificationUpdate(
                event_ids=[unknown.id, impact.id],
                primary_class_code="IMPACT",
                subclass_code="BALL_METAL",
                reason="Identische Klasse gemeinsam bestätigt",
            ),
            db,
            user,
        )
        assert len(results) == 2
        assert review_summary(db, user).completed_recognized == 2
        assert len(list(db.scalars(select(EventClassificationRevision)))) == 2


def test_review_run_updates_automatic_events_and_keeps_manual_assignments(
    tmp_path, monkeypatch
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'review.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(review_service, "SessionLocal", factory)
    with factory() as db:
        automatic = event("Dog")
        automatic.category = "ANIMAL"
        manual = event("Dog", "IMPACT")
        manual.classification_status = "manual"
        run = ReviewRun(kind="automatic", requested_by="operator")
        db.add_all([automatic, manual, run])
        db.commit()
        run_id, automatic_id, manual_id = run.id, automatic.id, manual.id

    review_service.process_review_run(run_id, batch_size=1)

    with factory() as db:
        assert db.get(ReviewRun, run_id).status == "completed"
        assert db.get(Event, automatic_id).primary_class_code == "DOG"
        assert db.get(Event, manual_id).primary_class_code == "IMPACT"


def test_noise_assessment_uses_evening_reference_and_sunday_surcharge() -> None:
    weekday = assessment_for("2026-08-07T19:30:00+02:00", 34)
    sunday = assessment_for("2026-08-09T20:30:00+02:00", 30)

    assert weekday["period"] == "evening"
    assert weekday["reference_db"] == 35
    assert weekday["surcharge_db"] == 0
    assert sunday["surcharge_db"] == 6
    assert sunday["assessed_db"] == 36
    assert sunday["exceeded"] is True
