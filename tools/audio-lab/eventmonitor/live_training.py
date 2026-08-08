from __future__ import annotations

import hashlib
import io
import os
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import soundfile as sf


def import_live_training_example(
    conn: Any,
    library: str | Path,
    example: Mapping[str, object],
    payload: bytes,
) -> bool:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != example["clip_sha256"]:
        raise ValueError("Trainingsclip stimmt nicht mit dem Server-Hash überein")
    if conn.execute("SELECT 1 FROM recordings WHERE source_hash=?", (digest,)).fetchone():
        return False
    try:
        info = sf.info(io.BytesIO(payload))
    except RuntimeError as exc:
        raise ValueError("Ungültiger Trainingsclip") from exc
    if info.channels != 1 or info.samplerate != 16_000 or not 1 <= info.duration <= 10:
        raise ValueError("Trainingsclip muss 1-10 Sekunden Mono-Audio mit 16000 Hz enthalten")

    target_directory = Path(library) / "live-training"
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{digest}.wav"
    with tempfile.NamedTemporaryFile(dir=target_directory, suffix=".wav.tmp", delete=False) as file:
        temporary = Path(file.name)
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO recordings(
                source_path,source_hash,audio_path,started_at,duration_seconds,
                sample_rate,channels,imported_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                f"dashboard:event:{example['event_id']}",
                digest,
                str(target),
                example["timestamp"],
                float(info.duration),
                int(info.samplerate),
                int(info.channels),
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.execute(
            """
            INSERT INTO segments(
                recording_id,start_seconds,end_seconds,label,label_confidence,notes,labelled_at,
                original_start_seconds,original_end_seconds,base_class_code,fine_class_code,
                assignment_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'manual')
            """,
            (
                cursor.lastrowid,
                0.0,
                float(info.duration),
                example["label"],
                float(example["confidence"]),
                f"Bestätigtes Live-Ereignis #{example['event_id']} von {example['device_id']}",
                datetime.now(UTC).isoformat(),
                0.0,
                float(info.duration),
                example["primary_class_code"],
                example["subclass_code"],
            ),
        )
    return True
