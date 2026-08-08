from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
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


def _case_state(row: Any) -> dict[str, Any]:
    return {
        "title": row["title"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_seconds": row["duration_seconds"],
        "status": row["status"],
        "notes": row["notes"],
    }


def _revision_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _append_revision(
    conn: Any,
    case_id: int,
    action: str,
    actor: str,
    reason: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> None:
    actor, reason = " ".join(actor.split()), " ".join(reason.split())
    if not actor or len(actor) > 100:
        raise ValueError("Der Bearbeiter muss 1 bis 100 Zeichen lang sein.")
    if not reason or len(reason) > 500:
        raise ValueError("Die Änderungsbegründung muss 1 bis 500 Zeichen lang sein.")
    previous = conn.execute(
        """
        SELECT revision_number,revision_hash FROM case_revisions
        WHERE case_id=? ORDER BY revision_number DESC LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    revision_number = int(previous["revision_number"] + 1) if previous else 1
    previous_hash = previous["revision_hash"] if previous else None
    created_at = datetime.now(UTC).isoformat()
    payload = {
        "case_id": case_id,
        "revision_number": revision_number,
        "action": action,
        "actor": actor,
        "reason": reason,
        "before": before,
        "after": after,
        "previous_hash": previous_hash,
        "created_at": created_at,
    }
    conn.execute(
        """
        INSERT INTO case_revisions(
            case_id,revision_number,action,actor,reason,before_json,after_json,
            previous_hash,revision_hash,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            case_id,
            revision_number,
            action,
            actor,
            reason,
            json.dumps(before, ensure_ascii=False, sort_keys=True) if before else None,
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            previous_hash,
            _revision_hash(payload),
            created_at,
        ),
    )


def create_case(
    conn: Any,
    title: str,
    event_ids: Iterable[int],
    *,
    actor: str = "audiolab-local",
    reason: str = "Case erstellt",
) -> int:
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
        created = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        _append_revision(conn, case_id, "created", actor, reason, None, _case_state(created))
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


def update_case(
    conn: Any,
    case_id: int,
    *,
    title: str,
    notes: str,
    status: str,
    actor: str,
    reason: str,
) -> None:
    if status not in {"draft", "confirmed", "rejected"}:
        raise ValueError("Ungültiger Case-Status.")
    if len(notes) > 10_000:
        raise ValueError("Die Notiz darf höchstens 10.000 Zeichen enthalten.")
    current = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if current is None:
        raise ValueError("Der Case wurde nicht gefunden.")
    before = _case_state(current)
    after = before | {"title": _clean_title(title), "notes": notes.strip(), "status": status}
    if after == before:
        raise ValueError("Es wurden keine Änderungen vorgenommen.")
    try:
        conn.execute(
            """
            UPDATE cases SET title=?,notes=?,status=?,updated_at=? WHERE id=?
            """,
            (after["title"], after["notes"], status, datetime.now(UTC).isoformat(), case_id),
        )
        _append_revision(conn, case_id, "updated", actor, reason, before, after)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def case_history(conn: Any, case_id: int) -> list[Any]:
    return conn.execute(
        "SELECT * FROM case_revisions WHERE case_id=? ORDER BY revision_number", (case_id,)
    ).fetchall()


def verify_case_history(conn: Any, case_id: int) -> bool:
    previous_hash = None
    latest_after = None
    for row in case_history(conn, case_id):
        if row["previous_hash"] != previous_hash:
            return False
        payload = {
            "case_id": case_id,
            "revision_number": row["revision_number"],
            "action": row["action"],
            "actor": row["actor"],
            "reason": row["reason"],
            "before": json.loads(row["before_json"]) if row["before_json"] else None,
            "after": json.loads(row["after_json"]),
            "previous_hash": row["previous_hash"],
            "created_at": row["created_at"],
        }
        if _revision_hash(payload) != row["revision_hash"]:
            return False
        previous_hash = row["revision_hash"]
        latest_after = payload["after"]
    current = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    return (
        previous_hash is not None and current is not None and latest_after == _case_state(current)
    )


def ensure_case_histories(conn: Any) -> int:
    cases = conn.execute(
        """
        SELECT c.* FROM cases c
        WHERE NOT EXISTS (SELECT 1 FROM case_revisions r WHERE r.case_id=c.id)
        """
    ).fetchall()
    for case in cases:
        _append_revision(
            conn,
            case["id"],
            "migration_snapshot",
            "audiolab-system",
            "Bestehenden Case in die Revisionshistorie übernommen",
            None,
            _case_state(case),
        )
    conn.commit()
    return len(cases)
