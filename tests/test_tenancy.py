import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.events import verify_ingest_key
from app.database.base import Base
from app.models.dashboard import Device, DeviceCredential, Tenant
from app.models.event import Event


def make_event(device: str) -> Event:
    return Event(
        timestamp="2026-08-11T12:00:00+02:00",
        event_type="AUDIO",
        label="Speech",
        label_de="Sprache",
        category="VOICE",
        confidence=0.8,
        db_level=45,
        device=device,
    )


def test_session_isolates_reads_and_assigns_tenant() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, name="A", slug="a"), Tenant(id=2, name="B", slug="b")])
        db.commit()
        db.info["tenant_id"] = 1
        first = make_event("mic-a")
        db.add(first)
        db.commit()
        assert first.tenant_id == 1
        db.info["tenant_id"] = 2
        second = make_event("mic-b")
        db.add(second)
        db.commit()
        assert second.tenant_id == 2
        assert [row.device for row in db.scalars(select(Event))] == ["mic-b"]
        db.info["tenant_id"] = 1
        assert [row.device for row in db.scalars(select(Event))] == ["mic-a"]


def test_device_secret_selects_tenant_and_cannot_impersonate_device() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    secret = "a-secure-device-secret"
    with Session(engine) as db:
        db.add_all([Tenant(id=1, name="A", slug="a"), Tenant(id=2, name="B", slug="b")])
        db.add(DeviceCredential(tenant_id=2, device_id="mic-b", secret_hash=hashlib.sha256(secret.encode()).hexdigest()))
        db.commit()
        verify_ingest_key(db, x_device_id="mic-b", x_device_secret=secret)
        assert db.info["tenant_id"] == 2
        assert db.info["authenticated_device_id"] == "mic-b"
        with pytest.raises(HTTPException) as error:
            verify_ingest_key(db, x_device_id="mic-b", x_device_secret="wrong")
        assert error.value.status_code == 401


def test_same_profile_name_is_allowed_in_separate_tenants() -> None:
    from app.models.dashboard import PersonProfile

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, name="A", slug="a"), Tenant(id=2, name="B", slug="b")])
        db.commit()
        db.info["tenant_id"] = 1
        db.add(PersonProfile(name="Person 1"))
        db.commit()
        db.info["tenant_id"] = 2
        db.add(PersonProfile(name="Person 1"))
        db.commit()
        assert len(list(db.scalars(select(PersonProfile)))) == 1
