import sys
from pathlib import Path

import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

import eventmonitor.model_registry as registry  # noqa: E402
from eventmonitor.db import connect  # noqa: E402
from eventmonitor.model_registry import (  # noqa: E402
    activate_model,
    active_model,
    archive_model,
    register_model,
    rollback_model,
)


def _artifact(path: Path, name: str) -> tuple[Path, dict]:
    model_path = path / f"{name}.joblib"
    model_path.write_bytes(b"local-model")
    return model_path, {
        "artifact_version": "1.0.0",
        "pipeline_fingerprint": f"pipeline-{name}",
        "metrics": {"test": {"macro_f1": 0.8}},
    }


def test_activation_and_rollback_preserve_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "registry.sqlite3")
    monkeypatch.setattr(registry, "load_model", lambda path: {"path": path})
    first_path, first_artifact = _artifact(tmp_path, "first")
    second_path, second_artifact = _artifact(tmp_path, "second")
    first = register_model(conn, first_path, first_artifact)
    second = register_model(conn, second_path, second_artifact)
    activate_model(conn, first)
    activate_model(conn, second)
    assert active_model(conn)["id"] == second
    assert rollback_model(conn) == first
    assert active_model(conn)["id"] == first
    reasons = [row[0] for row in conn.execute("SELECT reason FROM model_activations ORDER BY id")]
    assert reasons[-1] == f"rollback_from:{second}"
    with pytest.raises(ValueError, match="aktive Modell"):
        archive_model(conn, first)
    conn.close()


def test_archived_model_is_not_rollback_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "archive.sqlite3")
    monkeypatch.setattr(registry, "load_model", lambda path: {})
    first_path, artifact = _artifact(tmp_path, "first")
    second_path, second_artifact = _artifact(tmp_path, "second")
    first = register_model(conn, first_path, artifact)
    second = register_model(conn, second_path, second_artifact)
    activate_model(conn, first)
    activate_model(conn, second)
    archive_model(conn, first)
    with pytest.raises(ValueError, match="keine frühere"):
        rollback_model(conn)
    conn.close()
