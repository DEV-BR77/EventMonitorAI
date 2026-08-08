from types import SimpleNamespace

from app.services.calibration import calculate_recommended_offset


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
