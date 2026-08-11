import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.importer import import_package, resume_imports  # noqa: E402


def test_failed_import_is_journaled_and_can_be_retried() -> None:
    with tempfile.TemporaryDirectory(dir=Path(".pytest_cache")) as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "broken.zip"
        source.write_text("not a measurement package", encoding="utf-8")
        database = temp_path / "eventmonitor.sqlite3"
        library = temp_path / "library"

        with pytest.raises(ValueError):
            import_package(source, database, library)

        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                "SELECT status, attempts, error_message FROM import_jobs"
            ).fetchone()
        assert row is not None
        assert row[0] == "failed"
        assert row[1] == 1
        assert "db.csv" in row[2]

        results = resume_imports(database, library)

        assert results[0][2] == "Fehler"
        with closing(sqlite3.connect(database)) as connection:
            attempts = connection.execute("SELECT attempts FROM import_jobs").fetchone()[0]
        assert attempts == 2
