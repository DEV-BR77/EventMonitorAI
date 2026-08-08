from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.api.dashboard import sound_map, update_device
from app.database.base import Base
from app.models.dashboard import Device, DeviceTelemetry
from app.models.event import Event
from app.schemas.dashboard import DeviceUpdate
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_admin_can_update_microphone_metadata_and_status() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Device(device_id="esp32-test", name="Unbenannt"))
        db.commit()

        result = update_device(
            "esp32-test",
            DeviceUpdate(
                name="Mikrofon Garten",
                location="Nordwest-Ecke",
                position_x=23.5,
                position_y=71.0,
                enabled=False,
            ),
            db,
            SimpleNamespace(username="admin", role="admin"),
        )

        assert result.name == "Mikrofon Garten"
        assert result.location == "Nordwest-Ecke"
        assert result.position_x == 23.5
        assert result.position_y == 71.0
        assert result.enabled is False


@pytest.mark.parametrize("field,value", [("position_x", -0.1), ("position_y", 100.1)])
def test_microphone_position_must_stay_inside_map(field: str, value: float) -> None:
    data = {"name": "Mikrofon", field: value}

    with pytest.raises(ValidationError):
        DeviceUpdate(**data)


def test_sound_map_combines_position_live_level_and_event_statistics() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Device(device_id="mic", name="Garten", position_x=25, position_y=75))
        db.add(DeviceTelemetry(device_id="mic", db_level=48.5))
        db.add_all(
            Event(
                timestamp=datetime.now(UTC).isoformat(),
                event_type="AUDIO",
                label="Noise",
                label_de="Geräusch",
                category="OTHER",
                confidence=0.9,
                db_level=level,
                device="mic",
            )
            for level in (50.0, 60.0, 70.0)
        )
        db.commit()

        point = sound_map(db, SimpleNamespace(), days=30, threshold_db=55)[0]

        assert (point.position_x, point.position_y) == (25, 75)
        assert point.current_db == 48.5
        assert point.average_db == 60.0
        assert point.maximum_db == 70.0
        assert point.exceedances == 2
