from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS recordings (
 id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_hash TEXT NOT NULL UNIQUE,
 audio_path TEXT NOT NULL, started_at TEXT, duration_seconds REAL, sample_rate INTEGER,
 channels INTEGER, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS db_samples (
 id INTEGER PRIMARY KEY, recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 offset_seconds REAL NOT NULL, measured_at TEXT, current_dba REAL, max_dba REAL, average_dba REAL
);
CREATE INDEX IF NOT EXISTS idx_db_samples_rec_offset ON db_samples(recording_id, offset_seconds);
CREATE TABLE IF NOT EXISTS spectrum_bins (
 id INTEGER PRIMARY KEY, recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 spectrum_type TEXT NOT NULL, frequency_hz REAL NOT NULL, min_db REAL, max_db REAL, avg_db REAL
);
CREATE TABLE IF NOT EXISTS segments (
 id INTEGER PRIMARY KEY, recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
 start_seconds REAL NOT NULL, end_seconds REAL NOT NULL, peak_dba REAL, mean_dba REAL,
 event_score REAL, label TEXT, label_confidence REAL, notes TEXT, labelled_at TEXT,
 original_start_seconds REAL, original_end_seconds REAL, boundaries_updated_at TEXT,
 UNIQUE(recording_id, start_seconds, end_seconds)
);
CREATE INDEX IF NOT EXISTS idx_segments_queue ON segments(label, event_score, peak_dba);
CREATE TABLE IF NOT EXISTS predictions (
 id INTEGER PRIMARY KEY, segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
 model_name TEXT NOT NULL, predicted_label TEXT NOT NULL, confidence REAL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT,
 reviewed_label TEXT, was_correct INTEGER, uncertainty_score REAL,
 informativeness_score REAL, active_learning_score REAL
);
CREATE INDEX IF NOT EXISTS idx_predictions_segment_created
ON predictions(segment_id, created_at DESC);
CREATE TABLE IF NOT EXISTS segment_embeddings (
 id INTEGER PRIMARY KEY, segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
 model_name TEXT NOT NULL, pipeline_fingerprint TEXT NOT NULL, dimension INTEGER NOT NULL,
 vector BLOB NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(segment_id, model_name)
);
CREATE INDEX IF NOT EXISTS idx_segment_embeddings_model
ON segment_embeddings(model_name, pipeline_fingerprint);
CREATE TABLE IF NOT EXISTS persons (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS segment_person_assignments (
 id INTEGER PRIMARY KEY,
 segment_id INTEGER NOT NULL UNIQUE REFERENCES segments(id) ON DELETE CASCADE,
 person_id INTEGER NOT NULL REFERENCES persons(id), source TEXT NOT NULL,
 confidence REAL, confirmed INTEGER NOT NULL DEFAULT 1,
 assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_segment_person_person
ON segment_person_assignments(person_id, confirmed);
CREATE TABLE IF NOT EXISTS import_jobs (
 id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, source_hash TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1, recording_id INTEGER,
 error_message TEXT, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON import_jobs(status, started_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(segments)")}
    if "event_score" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN event_score REAL")
    if "original_start_seconds" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN original_start_seconds REAL")
    if "original_end_seconds" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN original_end_seconds REAL")
    if "boundaries_updated_at" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN boundaries_updated_at TEXT")
    conn.execute(
        """
        UPDATE segments
        SET original_start_seconds=COALESCE(original_start_seconds, start_seconds),
            original_end_seconds=COALESCE(original_end_seconds, end_seconds)
        WHERE original_start_seconds IS NULL OR original_end_seconds IS NULL
        """
    )
    prediction_cols = {r[1] for r in conn.execute("PRAGMA table_info(predictions)")}
    for name, definition in (
        ("reviewed_at", "TEXT"),
        ("reviewed_label", "TEXT"),
        ("was_correct", "INTEGER"),
        ("uncertainty_score", "REAL"),
        ("informativeness_score", "REAL"),
        ("active_learning_score", "REAL"),
    ):
        if name not in prediction_cols:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {name} {definition}")
    conn.commit()
    return conn
