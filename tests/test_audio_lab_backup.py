import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.backup import create_backup, restore_backup  # noqa: E402
from eventmonitor.db import connect  # noqa: E402


def _library(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "source.sqlite3"
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"RIFF-test-audio")
    conn = connect(db_path)
    conn.execute(
        """
        INSERT INTO recordings(source_path,source_hash,audio_path,duration_seconds)
        VALUES ('source.zip','abc',?,1.0)
        """,
        (str(audio),),
    )
    conn.execute(
        "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) VALUES (1,0,1,'Hupe')"
    )
    conn.commit()
    conn.close()
    return db_path, audio


def test_backup_round_trip_rewrites_audio_location(tmp_path: Path) -> None:
    source_db, _ = _library(tmp_path)
    backup = create_backup(source_db, tmp_path / "portable.emabackup")
    target_db = tmp_path / "new" / "eventmonitor.sqlite3"
    target_db.parent.mkdir()
    count, recovery = restore_backup(backup, target_db, tmp_path / "new-library")
    assert count == 1
    assert recovery is None
    conn = sqlite3.connect(target_db)
    row = conn.execute(
        "SELECT r.audio_path,s.label FROM recordings r JOIN segments s ON s.recording_id=r.id"
    ).fetchone()
    conn.close()
    assert Path(row[0]).parent == tmp_path / "new-library"
    assert Path(row[0]).read_bytes() == b"RIFF-test-audio"
    assert row[1] == "Hupe"


def test_restore_rejects_changed_payload(tmp_path: Path) -> None:
    source_db, _ = _library(tmp_path)
    backup = create_backup(source_db, tmp_path / "portable.emabackup")
    changed = tmp_path / "changed.emabackup"
    with zipfile.ZipFile(backup) as source, zipfile.ZipFile(changed, "w") as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            target.writestr(info, b"changed" if info.filename.startswith("library/") else payload)
    with pytest.raises(ValueError, match="Prüfsumme"):
        restore_backup(changed, tmp_path / "target.sqlite3", tmp_path / "library")
