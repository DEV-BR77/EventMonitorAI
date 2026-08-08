from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eventmonitor.training import load_model


def register_model(conn: Any, artifact_path: str | Path, artifact: dict[str, Any]) -> int:
    path = Path(artifact_path).resolve()
    if not path.is_file():
        raise ValueError("Das Modellartefakt wurde nicht gefunden.")
    required = {"artifact_version", "pipeline_fingerprint", "metrics"}
    if not required <= artifact.keys():
        raise ValueError("Das Modellartefakt enthält nicht alle Registrierungsdaten.")
    cursor = conn.execute(
        """
        INSERT INTO model_registry(
            name,artifact_path,artifact_version,pipeline_fingerprint,metrics_json
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(artifact_path) DO UPDATE SET
            artifact_version=excluded.artifact_version,
            pipeline_fingerprint=excluded.pipeline_fingerprint,
            metrics_json=excluded.metrics_json
        RETURNING id
        """,
        (
            path.name,
            str(path),
            artifact["artifact_version"],
            artifact["pipeline_fingerprint"],
            json.dumps(artifact["metrics"]),
        ),
    )
    model_id = int(cursor.fetchone()[0])
    conn.commit()
    return model_id


def list_models(conn: Any) -> list[Any]:
    return conn.execute("SELECT * FROM model_registry ORDER BY created_at DESC,id DESC").fetchall()


def active_model(conn: Any) -> Any | None:
    return conn.execute("SELECT * FROM model_registry WHERE status='active' LIMIT 1").fetchone()


def activate_model(conn: Any, model_id: int, *, reason: str = "manual") -> None:
    model = conn.execute("SELECT * FROM model_registry WHERE id=?", (model_id,)).fetchone()
    if model is None:
        raise ValueError("Das Modell wurde nicht gefunden.")
    load_model(model["artifact_path"])
    now = datetime.now(UTC).isoformat()
    try:
        conn.execute("UPDATE model_registry SET status='available' WHERE status='active'")
        conn.execute(
            "UPDATE model_registry SET status='active',activated_at=? WHERE id=?", (now, model_id)
        )
        conn.execute(
            "INSERT INTO model_activations(model_id,reason,activated_at) VALUES (?,?,?)",
            (model_id, reason, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def archive_model(conn: Any, model_id: int) -> None:
    model = conn.execute("SELECT status FROM model_registry WHERE id=?", (model_id,)).fetchone()
    if model is None:
        raise ValueError("Das Modell wurde nicht gefunden.")
    if model["status"] == "active":
        raise ValueError("Das aktive Modell kann nicht archiviert werden.")
    conn.execute("UPDATE model_registry SET status='archived' WHERE id=?", (model_id,))
    conn.commit()


def rollback_model(conn: Any) -> int:
    current = active_model(conn)
    if current is None:
        raise ValueError("Es ist kein aktives Modell vorhanden.")
    previous = conn.execute(
        """
        SELECT a.model_id FROM model_activations a JOIN model_registry m ON m.id=a.model_id
        WHERE a.model_id<>? AND m.status<>'archived'
        ORDER BY a.activated_at DESC,a.id DESC LIMIT 1
        """,
        (current["id"],),
    ).fetchone()
    if previous is None:
        raise ValueError("Es gibt keine frühere aktivierbare Modellversion.")
    activate_model(conn, previous["model_id"], reason=f"rollback_from:{current['id']}")
    return int(previous["model_id"])
