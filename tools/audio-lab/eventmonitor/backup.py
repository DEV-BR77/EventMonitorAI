from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

BACKUP_FORMAT = 1
REQUIRED_TABLES = {"recordings", "db_samples", "spectrum_bins", "segments", "predictions"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_backup(db_path: str | Path, destination: str | Path) -> Path:
    db_path, destination = Path(db_path), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eventmonitor-backup-") as temporary:
        snapshot = Path(temporary) / "eventmonitor.sqlite3"
        source = sqlite3.connect(db_path)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        snapshot_db = sqlite3.connect(snapshot)
        audio_paths = [
            Path(row[0])
            for row in snapshot_db.execute("SELECT audio_path FROM recordings ORDER BY id")
        ]
        snapshot_db.close()
        files: dict[str, dict[str, int | str]] = {
            "database/eventmonitor.sqlite3": {
                "sha256": _sha256(snapshot),
                "size": snapshot.stat().st_size,
            }
        }
        audio_entries: list[tuple[Path, str]] = []
        for index, audio_path in enumerate(audio_paths):
            if not audio_path.is_file():
                raise FileNotFoundError(f"Audiodatei fehlt: {audio_path}")
            archive_name = f"library/{index:06d}-{audio_path.name}"
            files[archive_name] = {"sha256": _sha256(audio_path), "size": audio_path.stat().st_size}
            audio_entries.append((audio_path, archive_name))
        manifest = {
            "format": BACKUP_FORMAT,
            "created_at": datetime.now(UTC).isoformat(),
            "files": files,
            "audio_entries": [entry for _, entry in audio_entries],
        }
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "database/eventmonitor.sqlite3")
            for audio_path, archive_name in audio_entries:
                archive.write(audio_path, archive_name)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return destination


def restore_backup(
    backup_path: str | Path, db_path: str | Path, library_path: str | Path
) -> tuple[int, Path | None]:
    backup_path, db_path, library_path = Path(backup_path), Path(db_path), Path(library_path)
    with tempfile.TemporaryDirectory(
        prefix="eventmonitor-restore-", dir=db_path.parent
    ) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(backup_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != BACKUP_FORMAT:
                raise ValueError("Nicht unterstützte Backup-Version.")
            for name, metadata in manifest.get("files", {}).items():
                safe_name = PurePosixPath(name)
                if safe_name.is_absolute() or ".." in safe_name.parts:
                    raise ValueError("Das Backup enthält einen unsicheren Dateipfad.")
                target = staging.joinpath(*safe_name.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if (
                    target.stat().st_size != metadata["size"]
                    or _sha256(target) != metadata["sha256"]
                ):
                    raise ValueError(f"Prüfsumme stimmt nicht: {name}")

        restored_db = staging / "database" / "eventmonitor.sqlite3"
        check = sqlite3.connect(restored_db)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Die gesicherte Datenbank ist beschädigt.")
            tables = {
                row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not REQUIRED_TABLES <= tables:
                raise ValueError("Die Sicherung enthält kein vollständiges AudioLab-Datenmodell.")
            audio_entries = manifest.get("audio_entries", [])
            rows = check.execute("SELECT id FROM recordings ORDER BY id").fetchall()
            if len(rows) != len(audio_entries):
                raise ValueError("Audioindex und Datenbank passen nicht zusammen.")
            for row, archive_name in zip(rows, audio_entries, strict=True):
                final_audio = library_path / Path(archive_name).name
                check.execute(
                    "UPDATE recordings SET audio_path=? WHERE id=?", (str(final_audio), row[0])
                )
            check.commit()
        finally:
            check.close()

        library_path.mkdir(parents=True, exist_ok=True)
        recovery = None
        if db_path.exists():
            recovery = db_path.with_suffix(f".pre-restore-{datetime.now():%Y%m%d-%H%M%S}.sqlite3")
            shutil.copy2(db_path, recovery)
        for archive_name in manifest.get("audio_entries", []):
            source = staging.joinpath(*PurePosixPath(archive_name).parts)
            os.replace(source, library_path / source.name)
        os.replace(restored_db, db_path)
        return len(manifest.get("audio_entries", [])), recovery
