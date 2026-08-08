from pathlib import Path


def read_version() -> str:
    """Read the repository-wide release version in local and container layouts."""
    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    raise RuntimeError("EventMonitorAI VERSION file not found")


__version__ = read_version()
