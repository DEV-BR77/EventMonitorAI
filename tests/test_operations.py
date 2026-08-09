import json
import zipfile
from pathlib import Path

from scripts.build_release import build

ROOT = Path(__file__).resolve().parents[1]


def test_release_bundle_excludes_runtime_data_and_secrets(tmp_path: Path) -> None:
    archive, manifest = build(tmp_path)
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()

    assert metadata["sha256"]
    assert any(name.endswith("compose.yaml") for name in names)
    assert any(name.endswith("scripts/install.ps1") for name in names)
    assert any(name.endswith(".env.docker.example") for name in names)
    assert not any(name.endswith((".wav", ".db", ".sqlite", ".env")) for name in names)


def test_compose_contains_automatic_backup_with_read_only_clips() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "backup:" in compose
    assert "eventmonitor_clips_data:/data/clips:ro" in compose
    assert "BACKUP_RETENTION_DAYS" in compose
    assert "./backups:/backups" in compose


def test_restore_verifies_manifest_before_stopping_services() -> None:
    script = (ROOT / "scripts" / "restore.ps1").read_text(encoding="utf-8")

    checksum = script.index("Get-FileHash")
    force_gate = script.index("if (-not $Force)")
    stop_services = script.index("stop app backup")
    assert checksum < force_gate < stop_services
    assert "--exit-on-error" in script
