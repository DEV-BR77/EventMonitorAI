from datetime import UTC, datetime, timedelta

from app.api.dashboard import device_levels
from app.api.events import update_device_telemetry
from app.database.base import Base
from app.models.dashboard import Device, DeviceLevelSample, User
from app.schemas.dashboard import DeviceTelemetryWrite
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session


def telemetry(level: float) -> DeviceTelemetryWrite:
    return DeviceTelemetryWrite(
        device_id="mic-1",
        packets_received=100,
        packets_lost=0,
        db_level=level,
    )


def test_telemetry_is_sampled_at_most_every_five_seconds() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        update_device_telemetry(telemetry(42), db, None)
        update_device_telemetry(telemetry(44), db, None)

        assert db.scalar(select(func.count()).select_from(DeviceLevelSample)) == 1


def test_level_history_is_aggregated_in_five_second_intervals() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="viewer", password_hash="x", role="viewer")
        device = Device(device_id="mic-1", name="Hofeinfahrt")
        minute = datetime.now(UTC).replace(second=0, microsecond=0)
        db.add_all(
            [
                user,
                device,
                DeviceLevelSample(
                    device_id="mic-1",
                    timestamp=(minute + timedelta(seconds=5)).isoformat(),
                    db_level=40,
                ),
                DeviceLevelSample(
                    device_id="mic-1",
                    timestamp=(minute + timedelta(seconds=8)).isoformat(),
                    db_level=50,
                ),
            ]
        )
        db.commit()

        result = device_levels(db, user, minutes=10)

        assert len(result) == 1
        assert result[0].name == "Hofeinfahrt"
        assert result[0].average_db == 45
        assert result[0].maximum_db == 50
