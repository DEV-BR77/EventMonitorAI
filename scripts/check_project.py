from __future__ import annotations

import compileall
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pio"}
BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".wav", ".mp3", ".flac"}


def check_python() -> bool:
    targets = [ROOT / "backend" / "app", ROOT / "edge", ROOT / "tools" / "audio-lab"]
    return all(compileall.compile_dir(path, quiet=1) for path in targets if path.exists())


def check_repository_hygiene() -> list[Path]:
    violations: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in BLOCKED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in BLOCKED_SUFFIXES:
            violations.append(path)
        if path.is_file() and path.name == ".env":
            violations.append(path)
    return violations


def main() -> int:
    ok = check_python()
    violations = check_repository_hygiene()
    if violations:
        print("Nicht versionierbare Dateien gefunden:")
        for path in violations:
            print(f"- {path.relative_to(ROOT)}")
        ok = False
    print("Projektprüfung erfolgreich." if ok else "Projektprüfung fehlgeschlagen.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
