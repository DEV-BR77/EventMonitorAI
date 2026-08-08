from app.models.dashboard import DeviceCalibration


def calculate_recommended_offset(calibration: DeviceCalibration) -> float:
    differences = []
    for level in ("low", "medium", "high"):
        reference = getattr(calibration, f"{level}_reference_db")
        measured = getattr(calibration, f"{level}_measured_db")
        if reference is not None and measured is not None:
            differences.append(reference - measured)
    return round(sum(differences) / len(differences), 2) if differences else 0.0
