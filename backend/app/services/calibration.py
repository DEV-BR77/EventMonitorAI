import csv
import io
from bisect import bisect_left
from datetime import datetime
from statistics import fmean
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dashboard import DeviceCalibration, DeviceLevelSample

BERLIN = ZoneInfo("Europe/Berlin")


def calculate_recommended_offset(calibration: DeviceCalibration) -> float:
    differences = []
    for level in ("low", "medium", "high"):
        reference = getattr(calibration, f"{level}_reference_db")
        measured = getattr(calibration, f"{level}_measured_db")
        if reference is not None and measured is not None:
            differences.append(reference - measured)
    return round(sum(differences) / len(differences), 2) if differences else 0.0


def calibrated_db(db: Session, device_id: str, raw_db: float) -> float:
    calibration = db.scalar(
        select(DeviceCalibration).where(DeviceCalibration.device_id == device_id)
    )
    offset = calibration.applied_offset_db if calibration is not None else 0.0
    return round(max(0.0, raw_db + offset), 2)


def _reference_time(value: str) -> datetime:
    cleaned = value.strip().replace("Z", "+00:00")
    parsed: datetime | None = None
    for pattern in (None, "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            parsed = (
                datetime.fromisoformat(cleaned)
                if pattern is None
                else datetime.strptime(cleaned, pattern)
            )
            break
        except ValueError:
            continue
    if parsed is None:
        for pattern in ("%H:%M:%S", "%H:%M"):
            try:
                clock = datetime.strptime(cleaned, pattern).time()
                parsed = datetime.now(BERLIN).replace(
                    hour=clock.hour, minute=clock.minute, second=clock.second, microsecond=0
                )
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError(f"Ungültiger Zeitstempel: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BERLIN)
    return parsed.astimezone(ZoneInfo("UTC"))


def parse_reference_csv(payload: bytes) -> list[tuple[datetime, float]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV muss UTF-8-kodiert sein") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV enthält keine Kopfzeile")
    headers = {name.strip().casefold(): name for name in reader.fieldnames}
    time_key = next(
        (headers[key] for key in ("timestamp", "zeitstempel", "zeit", "uhrzeit") if key in headers),
        None,
    )
    db_key = next(
        (
            headers[key]
            for key in ("reference_db", "referenz_db", "db_level", "dezibel", "db")
            if key in headers
        ),
        None,
    )
    if time_key is None or db_key is None:
        raise ValueError(
            "CSV benötigt timestamp (oder zeit/uhrzeit) und reference_db (oder db_level/dezibel)"
        )
    points: list[tuple[datetime, float]] = []
    for line, row in enumerate(reader, start=2):
        if not (row.get(time_key) or "").strip() and not (row.get(db_key) or "").strip():
            continue
        try:
            value = float((row.get(db_key) or "").strip().replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"Zeile {line}: ungültiger Referenzpegel") from exc
        if not 0 <= value <= 140:
            raise ValueError(f"Zeile {line}: Referenzpegel muss zwischen 0 und 140 dB liegen")
        points.append((_reference_time(row.get(time_key) or ""), value))
    if len(points) < 12:
        raise ValueError("CSV benötigt mindestens 12 Referenzwerte (etwa eine Minute)")
    points.sort(key=lambda item: item[0])
    return points


def compare_reference_points(
    samples: list[DeviceLevelSample],
    reference: list[tuple[datetime, float]],
    tolerance_seconds: float,
    current_offset: float,
) -> dict[str, float | int]:
    reference_seconds = [point[0].timestamp() for point in reference]
    pairs: list[tuple[float, float]] = []
    for sample in samples:
        sample_time = _reference_time(sample.timestamp).timestamp()
        index = bisect_left(reference_seconds, sample_time)
        candidates = [item for item in (index - 1, index) if 0 <= item < len(reference)]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda item: abs(reference_seconds[item] - sample_time))
        if abs(reference_seconds[nearest] - sample_time) <= tolerance_seconds:
            pairs.append((reference[nearest][1], sample.db_level))
    if len(pairs) < 6:
        raise ValueError("Zu wenige zeitgleiche Mikrofonwerte gefunden (mindestens 6 erforderlich)")
    differences = [reference_db - measured_db for reference_db, measured_db in pairs]
    mean_reference = fmean(item[0] for item in pairs)
    mean_measured = fmean(item[1] for item in pairs)
    mean_difference = fmean(differences)
    return {
        "matched_points": len(pairs),
        "mean_reference_db": round(mean_reference, 2),
        "mean_measured_db": round(mean_measured, 2),
        "mean_difference_db": round(mean_difference, 2),
        "mae_db": round(fmean(abs(item) for item in differences), 2),
        "recommended_offset_db": round(max(-30.0, min(30.0, current_offset + mean_difference)), 2),
    }
