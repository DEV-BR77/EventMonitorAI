import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.api.dashboard import apply_calibration_offsets, import_calibration_reference
from app.database.base import Base
from app.models.dashboard import (
    Device,
    DeviceCalibration,
    DeviceLevelSample,
    DeviceTelemetry,
    User,
)
from app.models.event import Event
from app.schemas.dashboard import CalibrationOffsetApply, CalibrationReferenceImport
from app.services.calibration import (
    calculate_recommended_offset,
    compare_reference_points,
    parse_reference_csv,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_recommended_offset_averages_available_reference_levels() -> None:
    calibration = SimpleNamespace(
        low_reference_db=35.0,
        low_measured_db=32.0,
        medium_reference_db=60.0,
        medium_measured_db=58.0,
        high_reference_db=85.0,
        high_measured_db=86.0,
    )

    assert calculate_recommended_offset(calibration) == 1.33


def test_recommended_offset_ignores_levels_not_yet_captured() -> None:
    calibration = SimpleNamespace(
        low_reference_db=35.0,
        low_measured_db=34.0,
        medium_reference_db=None,
        medium_measured_db=None,
        high_reference_db=None,
        high_measured_db=None,
    )

    assert calculate_recommended_offset(calibration) == 1.0


def _reference_csv(start: datetime, value: float = 45.0) -> bytes:
    rows = ["timestamp;reference_db"]
    for index in range(12):
        rows.append(f"{(start + timedelta(seconds=index * 5)).isoformat()};{value:.1f}")
    return "\n".join(rows).encode()


def test_reference_csv_is_parsed_and_compared_by_timestamp() -> None:
    start = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)
    reference = parse_reference_csv(_reference_csv(start))
    samples = [
        SimpleNamespace(
            timestamp=(start + timedelta(seconds=index * 5 + 1)).isoformat(),
            db_level=52.0,
        )
        for index in range(12)
    ]

    result = compare_reference_points(samples, reference, 2.0, 0.0)

    assert result["matched_points"] == 12
    assert result["mean_difference_db"] == -7.0
    assert result["recommended_offset_db"] == -7.0
    assert result["mae_db"] == 7.0


def test_existing_sound_meter_csv_format_is_accepted_without_conversion() -> None:
    rows = ["Date,Time,Current (dB-A),Max (dB-A), Average (dB-A)"]
    rows.extend(f"09.08.2026,13:55:{second:02d},{43 + second % 4},50,47" for second in range(12))

    reference = parse_reference_csv("\n".join(rows).encode("utf-8"))

    assert len(reference) == 12
    assert reference[0][0].astimezone(UTC).isoformat() == "2026-08-09T11:55:00+00:00"
    assert reference[0][1] == 43.0


def test_reference_import_persists_comparison_and_applies_offset() -> None:
    start = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="admin", password_hash="x", role="admin")
        db.add_all([user, Device(device_id="mic", name="Mic")])
        db.add_all(
            DeviceLevelSample(
                device_id="mic",
                timestamp=(start + timedelta(seconds=index * 5)).isoformat(),
                db_level=51.0,
            )
            for index in range(12)
        )
        event = Event(
            timestamp=start.isoformat(),
            event_type="AUDIO",
            label="Test",
            label_de="Test",
            category="OTHER",
            confidence=0.8,
            db_level=55.0,
            avg_db_level=53.0,
            device="mic",
        )
        telemetry = DeviceTelemetry(device_id="mic", db_level=52.0)
        db.add_all([event, telemetry])
        db.commit()

        run = import_calibration_reference(
            CalibrationReferenceImport(
                filename="referenz.csv",
                content_base64=base64.b64encode(_reference_csv(start, 46.0)).decode(),
                device_ids=["mic"],
                tolerance_seconds=2,
            ),
            db,
            user,
        )

        assert run.results[0].matched_points == 12
        assert run.results[0].recommended_offset_db == -5.0
        calibration = db.scalar(
            select(DeviceCalibration).where(DeviceCalibration.device_id == "mic")
        )
        assert calibration is not None
        assert calibration.applied_offset_db == 0
        apply_calibration_offsets(CalibrationOffsetApply(device_ids=["mic"]), db, user)
        assert calibration.applied_offset_db == -5.0
        assert event.db_level == 50.0
        assert event.avg_db_level == 48.0
        assert telemetry.db_level == 47.0
        assert db.scalar(select(DeviceLevelSample).order_by(DeviceLevelSample.id)).db_level == 46.0

        apply_calibration_offsets(CalibrationOffsetApply(device_ids=["mic"]), db, user)
        assert event.db_level == 50.0
