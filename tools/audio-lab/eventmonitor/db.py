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
 UNIQUE(recording_id, start_seconds, end_seconds)
);
CREATE INDEX IF NOT EXISTS idx_segments_queue ON segments(label, event_score, peak_dba);
CREATE TABLE IF NOT EXISTS predictions (
 id INTEGER PRIMARY KEY, segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
 model_name TEXT NOT NULL, predicted_label TEXT NOT NULL, confidence REAL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def connect(path: str | Path) -> sqlite3.Connection:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p); conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute('PRAGMA table_info(segments)')}
    if 'event_score' not in cols:
        conn.execute('ALTER TABLE segments ADD COLUMN event_score REAL')
    conn.commit()
    return conn
