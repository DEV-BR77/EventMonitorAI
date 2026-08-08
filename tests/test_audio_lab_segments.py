import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

AUDIO_LAB_DIR = Path(__file__).parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.segments import (  # noqa: E402
    update_boundaries,
    validate_boundaries,
    wav_excerpt,
)


def test_boundary_validation_rejects_invalid_ranges() -> None:
    assert validate_boundaries(1.2345, 2.3456, 10) == (1.234, 2.346)
    with pytest.raises(ValueError):
        validate_boundaries(-1, 2, 10)
    with pytest.raises(ValueError):
        validate_boundaries(3, 2, 10)
    with pytest.raises(ValueError):
        validate_boundaries(1, 11, 10)


def test_update_boundaries_recalculates_metrics() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE segments (id INTEGER PRIMARY KEY, recording_id INTEGER, start_seconds REAL,
          end_seconds REAL, peak_dba REAL, mean_dba REAL, event_score REAL,
          boundaries_updated_at TEXT, UNIQUE(recording_id,start_seconds,end_seconds));
        CREATE TABLE db_samples (recording_id INTEGER, offset_seconds REAL, current_dba REAL);
        INSERT INTO segments VALUES (1,7,0,5,NULL,NULL,NULL,NULL);
        INSERT INTO db_samples VALUES (7,0,30),(7,1,40),(7,2,50),(7,3,60);
        """
    )
    update_boundaries(conn, 1, 1, 3, 4)
    row = conn.execute("SELECT * FROM segments").fetchone()
    assert row[2:7] == pytest.approx((1, 3, 50, 45, 5))
    assert row[7]


def test_wav_excerpt_has_requested_duration() -> None:
    sample_rate = 8_000
    audio = np.zeros((sample_rate * 2, 1), dtype=np.float32)
    payload = wav_excerpt(audio, sample_rate, 0.25, 1.25)
    with sf.SoundFile(__import__("io").BytesIO(payload)) as clip:
        assert clip.frames == sample_rate
        assert clip.samplerate == sample_rate
