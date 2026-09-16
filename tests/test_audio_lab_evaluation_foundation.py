import json
import sys
from pathlib import Path

import pytest

# ruff: noqa: E501

sys.path.insert(0, str(Path(__file__).parents[1] / "tools" / "audio-lab"))

from eventmonitor.db import connect
from eventmonitor.evaluation import add_sample, create_dataset, freeze_dataset, metrics


def _recording(conn, tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"RIFF-test-input")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at,duration_seconds,sample_rate,channels) VALUES (?,?,?,?,?,?,?)",
        ("source.wav", "source-hash", str(audio_path), "2026-09-16T10:00:00Z", 1, 16000, 1),
    )
    recording_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) VALUES (?,?,?,?)",
        (recording_id, 0, 1, "A"),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_golden_dataset_freeze_manifest_and_duplicate_protection(tmp_path):
    conn = connect(tmp_path / "evaluation.sqlite3")
    segment_id = _recording(conn, tmp_path)
    dataset_id = create_dataset(conn, "golden-audio", "Golden Audio v1")
    add_sample(conn, dataset_id, segment_id, "A", "confirmed", "human_review")
    fingerprint = freeze_dataset(conn, dataset_id)
    row = conn.execute("SELECT frozen,manifest_json,fingerprint FROM evaluation_datasets WHERE id=?", (dataset_id,)).fetchone()
    assert row[0] == 1
    assert json.loads(row[1])["samples"][0]["segment_id"] == segment_id
    assert row[2] == fingerprint
    with pytest.raises(ValueError, match="unveränderlich"):
        add_sample(conn, dataset_id, segment_id, "A", "confirmed", "human_review")


def test_metrics_include_macro_weighted_micro_and_support_warning():
    result = metrics(["A", "A", "B"], ["A", "B", "B"], ["A", "B"])
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert "macro_f1" in result and "weighted_f1" in result and "micro_f1" in result
    assert result["support_warnings"] == ["A", "B"]
