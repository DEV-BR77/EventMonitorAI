import sys
from pathlib import Path

import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.db import connect  # noqa: E402
from eventmonitor.events import GroupingPolicy, group_segments, rebuild_events  # noqa: E402


def _segment(identifier, start, end, label, recording=1, peak=50, mean=45):
    return {
        "id": identifier,
        "recording_id": recording,
        "start_seconds": start,
        "end_seconds": end,
        "label": label,
        "peak_dba": peak,
        "mean_dba": mean,
    }


def test_grouping_uses_special_vocal_and_impulse_windows() -> None:
    groups = group_segments(
        [
            _segment(1, 0, 1, "Rufen"),
            _segment(2, 3.5, 4, "Schreien"),
            _segment(3, 8, 8.2, "Hupe"),
            _segment(4, 9.5, 9.7, "Schlagen / Aufprall"),
            _segment(5, 12, 13, "Hund"),
            _segment(6, 13.8, 14, "Hund"),
            _segment(7, 14.5, 15, "Musik"),
        ]
    )
    assert [group.segment_ids for group in groups] == [(1, 2), (3, 4), (5, 6), (7,)]
    assert [group.event_family for group in groups] == [
        "voice",
        "impulse",
        "label:Hund",
        "label:Musik",
    ]


def test_grouping_never_crosses_recording_boundary() -> None:
    groups = group_segments([_segment(1, 0, 1, "Rufen"), _segment(2, 1, 2, "Rufen", 2)])
    assert len(groups) == 2


def test_rebuild_is_idempotent_and_links_every_labelled_segment(tmp_path: Path) -> None:
    conn = connect(tmp_path / "events.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path) VALUES ('x','h','x.wav')"
    )
    conn.executemany(
        """
        INSERT INTO segments(recording_id,start_seconds,end_seconds,label,peak_dba,mean_dba)
        VALUES (1,?,?,?,?,?)
        """,
        [(0, 1, "Rufen", 50, 45), (2, 3, "Schreien", 60, 50), (10, 11, None, 40, 35)],
    )
    conn.commit()
    assert rebuild_events(conn, GroupingPolicy()) == 1
    assert rebuild_events(conn, GroupingPolicy()) == 1
    event = conn.execute("SELECT * FROM events").fetchone()
    assert event["segment_count"] == 2
    assert event["peak_dba"] == pytest.approx(60)
    assert conn.execute("SELECT COUNT(*) FROM event_segments").fetchone()[0] == 2
    conn.close()


def test_rebuild_preserves_manual_event_and_its_segment(tmp_path: Path) -> None:
    conn = connect(tmp_path / "manual-events.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path) VALUES ('x','h','x.wav')"
    )
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) "
        "VALUES (1,0,1,'Hund')"
    )
    event_id = conn.execute("""
        INSERT INTO events(
            recording_id,start_seconds,end_seconds,primary_label,event_family,
            grouping_version,segment_count,source
        ) VALUES (1,0,1,'Hund','label:Hund','manual',1,'manual')
        """).lastrowid
    conn.execute(
        "INSERT INTO event_segments(event_id,segment_id,position) VALUES (?,1,0)", (event_id,)
    )
    conn.commit()
    assert rebuild_events(conn) == 0
    assert conn.execute("SELECT source FROM events").fetchone()[0] == "manual"
    conn.close()
