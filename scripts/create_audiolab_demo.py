from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
AUDIO_LAB = ROOT / "tools" / "audio-lab"
sys.path.insert(0, str(AUDIO_LAB))

from eventmonitor.db import connect  # noqa: E402


def create_demo(target: Path) -> None:
    data_dir = target / "data"
    library = data_dir / "library"
    library.mkdir(parents=True, exist_ok=True)
    sample_rate = 16_000
    duration = 15
    time = np.arange(sample_rate * duration, dtype=np.float32) / sample_rate
    signal = (
        0.18 * np.sin(2 * np.pi * 440 * time)
        + 0.08 * np.sin(2 * np.pi * 1_000 * time) * (time > 5)
        + 0.25 * np.sin(2 * np.pi * 2_200 * time) * (time > 10)
    ).astype(np.float32)
    audio_path = library / "visual-test.wav"
    sf.write(audio_path, signal, sample_rate)

    connection = connect(data_dir / "eventmonitor.sqlite3")
    cursor = connection.execute(
        """
        INSERT INTO recordings(
            source_path, source_hash, audio_path, started_at,
            duration_seconds, sample_rate, channels
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "synthetic",
            "smoke-visualization",
            str(audio_path),
            "2026-08-08T10:55:00",
            duration,
            sample_rate,
            1,
        ),
    )
    recording_id = int(cursor.lastrowid)
    rows = []
    for offset in np.arange(0, duration, 0.2):
        level = (
            42
            + 5 * np.sin(offset / 2)
            + (12 if 5 <= offset < 7 else 0)
            + (20 if 10 <= offset < 11 else 0)
        )
        rows.append(
            (
                recording_id,
                float(offset),
                f"2026-08-08T10:55:{int(offset):02d}",
                float(level),
                float(level + 2),
                float(level - 1),
            )
        )
    connection.executemany(
        """
        INSERT INTO db_samples(
            recording_id, offset_seconds, measured_at,
            current_dba, max_dba, average_dba
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    for values in ((0, 5, 47, 43, 5), (5, 10, 59, 48, 17), (10, 15, 65, 50, 23)):
        connection.execute(
            """
            INSERT INTO segments(
                recording_id, start_seconds, end_seconds,
                peak_dba, mean_dba, event_score
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (recording_id, *values),
        )
    connection.commit()
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic AudioLab demo data")
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    create_demo(args.target.resolve())
    print(args.target.resolve())


if __name__ == "__main__":
    main()
