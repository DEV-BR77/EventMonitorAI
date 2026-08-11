import app.services.review as review_service
from app.api.events import bulk_classification, review_queue, review_summary
from app.database.base import Base
from app.models.dashboard import AudioClip, EventClassificationRevision, ReviewRun, User
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
        context_only = event("Imported metadata", "AMBIENT")
        context_only.classification_status = "context_only"
        db.add_all([user, unknown, impact, context_only])
        db.flush()
        db.add_all(
            [
                AudioClip(
                    device_id="mic",
                    trigger_id=f"trigger-{item.id}",
                    received_at=item.timestamp,
                    sha256=str(item.id).zfill(64),
                    path=f"audio/{item.id}.wav",
                    frame_count=16000,
                    sample_rate=16000,
                    event_id=item.id,
                )
                for item in (unknown, impact)
            ]
        )
        db.commit()

        before = review_summary(db, user)
        assert before.open_unknown == 1
        assert before.open_recognized == 1
        assert before.excluded_context_only == 1
        assert [item.id for item in review_queue(db, user, "UNKNOWN", "open", 20)] == [unknown.id]
        assert context_only.id not in [
            item.id for item in review_queue(db, user, None, "all", 20)
        ]

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
        context_only = event("Dog", "AMBIENT")
        context_only.classification_status = "context_only"
        run = ReviewRun(kind="automatic", requested_by="operator")
        db.add_all([automatic, manual, context_only, run])
        db.commit()
        run_id, automatic_id, manual_id, context_only_id = (
            run.id,
            automatic.id,
            manual.id,
            context_only.id,
        )

    review_service.process_review_run(run_id, batch_size=1)

    with factory() as db:
        assert db.get(ReviewRun, run_id).status == "completed"
        assert db.get(Event, automatic_id).primary_class_code == "DOG"
        assert db.get(Event, manual_id).primary_class_code == "IMPACT"
        assert db.get(Event, context_only_id).primary_class_code == "AMBIENT"


def test_clipless_events_become_context_only_without_changing_their_class() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        clipless = event("Dog", "DOG")
        clipped = event("Knock", "IMPACT")
        db.add_all([clipless, clipped])
        db.flush()
        db.add(
            AudioClip(
                device_id="mic",
                trigger_id="trigger-1",
                received_at="2026-08-08T20:30:00+02:00",
                sha256="a" * 64,
                path="audio/test.wav",
                frame_count=16000,
                sample_rate=16000,
                event_id=clipped.id,
            )
        )
        db.commit()

        assert review_service.mark_clipless_events_context_only(db) == 1
        assert clipless.classification_status == "context_only"
        assert clipless.primary_class_code == "DOG"
        assert clipped.classification_status == "automatic"
        revision = db.scalar(
            select(EventClassificationRevision).where(
                EventClassificationRevision.event_id == clipless.id
            )
        )
        assert revision is not None
        assert revision.status == "context_only"


def test_noise_assessment_uses_evening_reference_and_sunday_surcharge() -> None:
    weekday = assessment_for("2026-08-07T19:30:00+02:00", 34)
    sunday = assessment_for("2026-08-09T20:30:00+02:00", 30)

    assert weekday["period"] == "evening"
    assert weekday["reference_db"] == 35
    assert weekday["surcharge_db"] == 0
    assert sunday["surcharge_db"] == 6
    assert sunday["assessed_db"] == 36
    assert sunday["exceeded"] is True
