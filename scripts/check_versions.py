from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pattern = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?"
    if not re.fullmatch(pattern, version):
        print(f"Ungültige semantische Version: {version}")
        return 1

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    if not declared or declared.group(1) != version:
        print("pyproject.toml stimmt nicht mit VERSION überein.")
        return 1

    print(f"Komponentenversionen sind auf {version} vereinheitlicht.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
