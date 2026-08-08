import sys
from pathlib import Path

import numpy as np
import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.db import connect  # noqa: E402
from eventmonitor.embeddings import store_embeddings  # noqa: E402
from eventmonitor.people import (  # noqa: E402
    assessment_period,
    assign_person,
    create_person,
    current_assignment,
    person_statistics,
    rename_person,
    suggest_person,
)


def _segments(conn) -> None:
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at) "
        "VALUES ('x','h','x.wav','2026-08-08T20:00:00')"
    )
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) VALUES (1,0,2,'Rufen')"
    )
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) "
        "VALUES (1,3,4,'Schreien')"
    )
    conn.commit()


def test_person_crud_assignment_and_statistics(tmp_path: Path) -> None:
    conn = connect(tmp_path / "people.sqlite3")
    _segments(conn)
    person_id = create_person(conn, "  Person   Garten  ")
    rename_person(conn, person_id, "Person Nord")
    assign_person(conn, 1, person_id)
    assignment = current_assignment(conn, 1)
    assert assignment["name"] == "Person Nord"
    stats = person_statistics(conn)
    assert stats == [
        {
            "person_id": person_id,
            "person": "Person Nord",
            "assessment_period": "Abend (19–22 Uhr)",
            "category": "Rufen",
            "frequency": 1,
            "duration_seconds": 2.0,
        }
    ]
    with pytest.raises(ValueError, match="existiert bereits"):
        create_person(conn, "Person Nord")
    conn.close()


def test_embedding_profile_suggests_nearest_person(tmp_path: Path) -> None:
    conn = connect(tmp_path / "suggest.sqlite3")
    _segments(conn)
    north = create_person(conn, "Nord")
    south = create_person(conn, "Süd")
    assign_person(conn, 1, north)
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) VALUES (1,5,6,'Rufen')"
    )
    conn.commit()
    assign_person(conn, 3, south)
    vectors = np.asarray([[1, 0], [0.99, 0.01], [-1, 0]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    store_embeddings(conn, np.asarray([1, 2, 3]), vectors, "model", "pipeline")
    suggestion = suggest_person(conn, 2)
    assert suggestion["person_id"] == north
    assert suggestion["similarity"] > 0.99
    conn.close()


def test_assessment_period_boundaries() -> None:
    assert assessment_period("2026-01-01T05:59:00", 0).startswith("Nacht")
    assert assessment_period("2026-01-01T13:00:00", 0).startswith("Tagesruhe")
    assert assessment_period("2026-01-01T19:00:00", 0).startswith("Abend")
