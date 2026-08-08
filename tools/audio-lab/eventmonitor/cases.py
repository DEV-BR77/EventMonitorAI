from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any


def _clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    if not cleaned or len(cleaned) > 200:
        raise ValueError("Der Case-Titel muss 1 bis 200 Zeichen lang sein.")
    return cleaned


def _event_times(row: Any) -> tuple[datetime, datetime]:
    if not row["recording_started_at"]:
        raise ValueError(f"Ereignis #{row['id']} besitzt keinen absoluten Aufnahmezeitpunkt.")
    recording_start = datetime.fromisoformat(row["recording_started_at"].replace("Z", "+00:00"))
    return (
        recording_start + timedelta(seconds=float(row["start_seconds"])),
        recording_start + timedelta(seconds=float(row["end_seconds"])),
    )


def create_case(conn: Any, title: str, event_ids: Iterable[int]) -> int:
    event_ids = list(dict.fromkeys(int(value) for value in event_ids))
    if not event_ids:
        raise ValueError("Ein Case benötigt mindestens ein Teilereignis.")
    placeholders = ",".join("?" for _ in event_ids)
    rows = conn.execute(
        f"""
        SELECT e.*,r.started_at AS recording_started_at
        FROM events e JOIN recordings r ON r.id=e.recording_id
        WHERE e.id IN ({placeholders})
        """,
        event_ids,
    ).fetchall()
    if len(rows) != len(event_ids):
        raise ValueError("Mindestens ein ausgewähltes Ereignis wurde nicht gefunden.")
    occupied = conn.execute(
        f"SELECT event_id FROM case_events WHERE event_id IN ({placeholders})", event_ids
    ).fetchall()
    if occupied:
        raise ValueError("Mindestens ein Ereignis gehört bereits zu einem Case.")
    timed = [(row, *_event_times(row)) for row in rows]
    timed.sort(key=lambda item: (item[1], item[0]["id"]))
    started_at = min(item[1] for item in timed)
    ended_at = max(item[2] for item in timed)
    try:
        cursor = conn.execute(
            """
            INSERT INTO cases(title,started_at,ended_at,duration_seconds)
            VALUES (?,?,?,?)
            """,
            (
                _clean_title(title),
                started_at.isoformat(),
                ended_at.isoformat(),
                (ended_at - started_at).total_seconds(),
            ),
        )
        case_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO case_events(case_id,event_id,position) VALUES (?,?,?)",
            [(case_id, row["id"], position) for position, (row, _, _) in enumerate(timed)],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return case_id


def case_events(conn: Any, case_id: int) -> list[Any]:
    return conn.execute(
        """
        SELECT ce.position,e.id,e.primary_label,e.event_family,e.segment_count,
               e.start_seconds,e.end_seconds,r.started_at AS recording_started_at
        FROM case_events ce JOIN events e ON e.id=ce.event_id
        JOIN recordings r ON r.id=e.recording_id
        WHERE ce.case_id=? ORDER BY ce.position
        """,
        (case_id,),
    ).fetchall()
