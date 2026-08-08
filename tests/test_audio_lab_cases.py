import sys
from pathlib import Path

import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.cases import case_events, create_case  # noqa: E402
from eventmonitor.db import connect  # noqa: E402
from eventmonitor.events import rebuild_events  # noqa: E402


def _event(conn, recording_id: int, start: float, end: float, label: str) -> int:
    return conn.execute(
        """
        INSERT INTO events(
            recording_id,start_seconds,end_seconds,primary_label,event_family,
            grouping_version,segment_count
        ) VALUES (?,?,?,?,?,'1.0.0',1)
        """,
        (recording_id, start, end, label, f"label:{label}"),
    ).lastrowid


def test_case_calculates_absolute_bounds_and_orders_subevents(tmp_path: Path) -> None:
    conn = connect(tmp_path / "cases.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at) "
        "VALUES ('a','a','a.wav','2026-08-08T10:00:00')"
    )
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at) "
        "VALUES ('b','b','b.wav','2026-08-08T10:01:00')"
    )
    first = _event(conn, 1, 10, 20, "Rufen")
    second = _event(conn, 2, 0, 5, "Hupe")
    conn.commit()
    case_id = create_case(conn, "  Vorfall   Garten ", [second, first])
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    assert case["title"] == "Vorfall Garten"
    assert case["started_at"] == "2026-08-08T10:00:10"
    assert case["ended_at"] == "2026-08-08T10:01:05"
    assert case["duration_seconds"] == pytest.approx(55)
    assert [row["id"] for row in case_events(conn, case_id)] == [first, second]
    with pytest.raises(ValueError, match="bereits"):
        create_case(conn, "Doppelt", [first])
    conn.close()


def test_event_rebuild_preserves_case_linked_automatic_event(tmp_path: Path) -> None:
    conn = connect(tmp_path / "case-protection.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at) "
        "VALUES ('a','a','a.wav','2026-08-08T10:00:00')"
    )
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) "
        "VALUES (1,0,1,'Rufen')"
    )
    conn.commit()
    rebuild_events(conn)
    event_id = conn.execute("SELECT id FROM events").fetchone()[0]
    create_case(conn, "Geschützt", [event_id])
    assert rebuild_events(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM case_events").fetchone()[0] == 1
    conn.close()
