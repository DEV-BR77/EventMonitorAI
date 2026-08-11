from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 100:
        raise ValueError("Der Personenname muss 1 bis 100 Zeichen lang sein.")
    return cleaned


def create_person(conn: Any, name: str) -> int:
    try:
        cursor = conn.execute("INSERT INTO persons(name) VALUES (?)", (_clean_name(name),))
        conn.commit()
    except Exception as error:
        conn.rollback()
        if "UNIQUE" in str(error):
            raise ValueError("Dieser Personenname existiert bereits.") from error
        raise
    return int(cursor.lastrowid)


def rename_person(conn: Any, person_id: int, name: str) -> None:
    try:
        cursor = conn.execute(
            "UPDATE persons SET name=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (_clean_name(name), person_id),
        )
    except Exception as error:
        conn.rollback()
        if "UNIQUE" in str(error):
            raise ValueError("Dieser Personenname existiert bereits.") from error
        raise
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError("Die Person wurde nicht gefunden.")
    conn.commit()


def set_person_active(conn: Any, person_id: int, active: bool) -> None:
    cursor = conn.execute(
        "UPDATE persons SET active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (int(active), person_id),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError("Die Person wurde nicht gefunden.")
    conn.commit()


def assign_person(
    conn: Any,
    segment_id: int,
    person_id: int | None,
    *,
    source: str = "manual",
    confidence: float | None = 1.0,
) -> None:
    if person_id is None:
        conn.execute("DELETE FROM segment_person_assignments WHERE segment_id=?", (segment_id,))
    else:
        conn.execute(
            """
            INSERT INTO segment_person_assignments(
                segment_id,person_id,source,confidence,confirmed,assigned_at
            ) VALUES (?,?,?,?,1,CURRENT_TIMESTAMP)
            ON CONFLICT(segment_id) DO UPDATE SET
                person_id=excluded.person_id,source=excluded.source,
                confidence=excluded.confidence,confirmed=1,assigned_at=CURRENT_TIMESTAMP
            """,
            (segment_id, person_id, source, confidence),
        )
    conn.commit()


def current_assignment(conn: Any, segment_id: int) -> Any | None:
    return conn.execute(
        """
        SELECT a.*,p.name FROM segment_person_assignments a
        JOIN persons p ON p.id=a.person_id WHERE a.segment_id=?
        """,
        (segment_id,),
    ).fetchone()


def suggest_person(conn: Any, segment_id: int) -> dict[str, Any] | None:
    source = conn.execute(
        "SELECT * FROM segment_embeddings WHERE segment_id=? ORDER BY created_at DESC LIMIT 1",
        (segment_id,),
    ).fetchone()
    if source is None:
        return None
    source_vector = np.frombuffer(source["vector"], dtype="<f4", count=source["dimension"])
    rows = conn.execute(
        """
        SELECT a.person_id,p.name,e.dimension,e.vector
        FROM segment_person_assignments a
        JOIN persons p ON p.id=a.person_id
        JOIN segment_embeddings e ON e.segment_id=a.segment_id
        WHERE a.confirmed=1 AND p.active=1 AND a.segment_id<>?
          AND e.model_name=? AND e.pipeline_fingerprint=?
        """,
        (segment_id, source["model_name"], source["pipeline_fingerprint"]),
    ).fetchall()
    grouped: dict[tuple[int, str], list[np.ndarray]] = defaultdict(list)
    for row in rows:
        if row["dimension"] == source["dimension"]:
            grouped[(row["person_id"], row["name"])].append(
                np.frombuffer(row["vector"], dtype="<f4", count=row["dimension"])
            )
    suggestions = []
    for (person_id, name), vectors in grouped.items():
        centroid = np.mean(vectors, axis=0)
        centroid /= max(float(np.linalg.norm(centroid)), 1e-12)
        suggestions.append(
            {
                "person_id": person_id,
                "name": name,
                "similarity": float(np.dot(source_vector, centroid)),
            }
        )
    return max(suggestions, key=lambda item: item["similarity"], default=None)


def assessment_period(started_at: str | None, offset_seconds: float) -> str:
    if not started_at:
        return "Zeit unbekannt"
    timestamp = datetime.fromisoformat(started_at.replace("Z", "+00:00")) + timedelta(
        seconds=offset_seconds
    )
    hour = timestamp.hour + timestamp.minute / 60
    if hour >= 22 or hour < 6:
        return "Nacht (22–06 Uhr)"
    if hour >= 19:
        return "Abend (19–22 Uhr)"
    if 13 <= hour < 15:
        return "Tagesruhe (13–15 Uhr)"
    return "Tag (06–13 / 15–19 Uhr)"


def person_statistics(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.id,p.name,s.label,s.start_seconds,s.end_seconds,r.started_at
        FROM segment_person_assignments a JOIN persons p ON p.id=a.person_id
        JOIN segments s ON s.id=a.segment_id JOIN recordings r ON r.id=s.recording_id
        WHERE a.confirmed=1 ORDER BY p.name,s.label,s.start_seconds
        """
    ).fetchall()
    totals: dict[tuple[int, str, str, str], dict[str, Any]] = {}
    for row in rows:
        period = assessment_period(row["started_at"], row["start_seconds"])
        category = row["label"] or "Unklassifiziert"
        key = (row["id"], row["name"], period, category)
        result = totals.setdefault(
            key,
            {
                "person_id": row["id"],
                "person": row["name"],
                "assessment_period": period,
                "category": category,
                "frequency": 0,
                "duration_seconds": 0.0,
            },
        )
        result["frequency"] += 1
        result["duration_seconds"] += float(row["end_seconds"] - row["start_seconds"])
    return list(totals.values())
