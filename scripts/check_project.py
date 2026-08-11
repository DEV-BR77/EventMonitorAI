from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    ".pio",
}
BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".wav", ".mp3", ".flac"}


def check_python() -> bool:
    targets = [ROOT / "backend" / "app", ROOT / "edge", ROOT / "tools" / "audio-lab"]
    return all(compileall.compile_dir(path, quiet=1) for path in targets if path.exists())


def check_repository_hygiene() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [Path(item) for item in result.stdout.decode().split("\0") if item]
    return [
        path
        for path in tracked
        if not any(part in BLOCKED_DIRS for part in path.parts)
        and (path.suffix.lower() in BLOCKED_SUFFIXES or path.name == ".env")
    ]


def main() -> int:
    ok = check_python()
    version_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_versions.py")],
        cwd=ROOT,
        check=False,
    )
    ok = ok and version_check.returncode == 0
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
