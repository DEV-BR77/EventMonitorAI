from __future__ import annotations

import io
import sqlite3
from datetime import datetime

import numpy as np
import soundfile as sf


def validate_boundaries(start: float, end: float, duration: float) -> tuple[float, float]:
    start, end, duration = float(start), float(end), float(duration)
    if duration <= 0:
        raise ValueError("Die Aufnahme hat keine gültige Dauer.")
    if start < 0 or end > duration:
        raise ValueError("Die Segmentgrenzen müssen innerhalb der Aufnahme liegen.")
    if end <= start:
        raise ValueError("Das Segmentende muss nach dem Segmentstart liegen.")
    return round(start, 3), round(end, 3)


def calculate_db_metrics(
    conn: sqlite3.Connection, recording_id: int, start: float, end: float
) -> tuple[float | None, float | None, float | None]:
    values = [
        float(row[0])
        for row in conn.execute(
            """
            SELECT current_dba FROM db_samples
            WHERE recording_id=? AND offset_seconds>=? AND offset_seconds<?
              AND current_dba IS NOT NULL
            """,
            (recording_id, start, end),
        )
    ]
    if not values:
        return None, None, None
    peak = max(values)
    mean = sum(values) / len(values)
    baseline_row = conn.execute(
        "SELECT current_dba FROM db_samples WHERE recording_id=? AND current_dba IS NOT NULL",
        (recording_id,),
    ).fetchall()
    baseline = float(np.median([float(row[0]) for row in baseline_row]))
    return peak, mean, peak - baseline


def update_boundaries(
    conn: sqlite3.Connection, segment_id: int, start: float, end: float, duration: float
) -> None:
    start, end = validate_boundaries(start, end, duration)
    segment = conn.execute("SELECT recording_id FROM segments WHERE id=?", (segment_id,)).fetchone()
    if segment is None:
        raise ValueError("Das Segment wurde nicht gefunden.")
    peak, mean, score = calculate_db_metrics(conn, int(segment[0]), start, end)
    try:
        conn.execute(
            """
            UPDATE segments SET start_seconds=?, end_seconds=?, peak_dba=?, mean_dba=?,
                event_score=?, boundaries_updated_at=? WHERE id=?
            """,
            (start, end, peak, mean, score, datetime.now().isoformat(), segment_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Ein Segment mit diesen Grenzen existiert bereits.") from exc


def wav_excerpt(data: np.ndarray, sample_rate: int, start: float, end: float) -> bytes:
    start, end = validate_boundaries(start, end, len(data) / sample_rate)
    first = max(0, round(start * sample_rate))
    last = min(len(data), round(end * sample_rate))
    output = io.BytesIO()
    sf.write(output, data[first:last], sample_rate, format="WAV", subtype="PCM_16")
    return output.getvalue()
