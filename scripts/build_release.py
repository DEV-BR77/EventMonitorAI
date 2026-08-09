from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    ".env.docker.example",
    "compose.yaml",
    "Dockerfile",
    "VERSION",
    "LICENSE",
    "README.md",
    "backend/app",
    "backend/requirements.txt",
    "frontend",
    "docs",
    "ops",
    "scripts/install.ps1",
    "scripts/upgrade.ps1",
    "scripts/backup.ps1",
    "scripts/restore.ps1",
)
EXCLUDED_SUFFIXES = {".pyc", ".wav", ".db", ".sqlite", ".env", ".zip"}


def release_files() -> list[Path]:
    files: set[Path] = set()
    for item in INCLUDE:
        source = ROOT / item
        if source.is_file():
            files.add(source)
        elif source.is_dir():
            files.update(path for path in source.rglob("*") if path.is_file())
    return sorted(
        path
        for path in files
        if (
            "__pycache__" not in path.parts
            and path.suffix.casefold() not in EXCLUDED_SUFFIXES
            and not path.name.startswith(".env.")
        )
        or path.name == ".env.docker.example"
    )


def build(target_directory: Path) -> tuple[Path, Path]:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    target_directory.mkdir(parents=True, exist_ok=True)
    archive = target_directory / f"EventMonitorAI-{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in release_files():
            bundle.write(path, Path(f"EventMonitorAI-{version}") / path.relative_to(ROOT))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = target_directory / f"EventMonitorAI-{version}.json"
    manifest.write_text(
        json.dumps(
            {"version": version, "archive": archive.name, "sha256": digest},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a secret-free EventMonitorAI release bundle"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()
    archive_path, manifest_path = build(arguments.output)
    print(archive_path)
    print(manifest_path)
