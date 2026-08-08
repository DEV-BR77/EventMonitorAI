from types import SimpleNamespace

import pytest
from app.api.dashboard import update_device
from app.database.base import Base
from app.models.dashboard import Device
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
