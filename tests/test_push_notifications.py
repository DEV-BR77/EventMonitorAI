from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.api.push import noise_log, respond
from app.database.base import Base
from app.models.dashboard import EventWitnessResponse, User
from app.models.event import Event
from app.services.push import decode_response_token, response_token
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_response_token_binds_user_and_event() -> None:
    token = response_token(12, 34)

    assert decode_response_token(token) == (12, 34)
    with pytest.raises(ValueError):
        decode_response_token(token + "changed")


def test_push_response_is_upserted_and_included_in_noise_log() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="witness", password_hash="x", role="viewer")
        event = Event(
            timestamp=datetime.now(UTC).isoformat(),
            event_type="AUDIO",
            label="Noise",
            label_de="Geräusch",
            category="OTHER",
            confidence=0.9,
            db_level=65,
            device="mic",
        )
        db.add_all([user, event])
        db.commit()

        first = respond(response_token(user.id, event.id), "confirmed", db)
        second = respond(response_token(user.id, event.id), "rejected", db)
        log = noise_log(db, SimpleNamespace(), limit=10)

        assert first.id == second.id
        assert db.scalar(select(EventWitnessResponse)).response == "rejected"
        assert log[0].event_id == event.id
        assert log[0].witnesses[0].username == "witness"
        assert log[0].witnesses[0].response == "rejected"
