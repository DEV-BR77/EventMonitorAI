from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from eventmonitor.features import FeaturePipelineConfig, extract_features
from eventmonitor.training import load_model

GROUND_TRUTH_STATUSES = {"confirmed", "uncertain", "unresolved"}


def input_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest(conn: Any, dataset_id: int) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT id,segment_id,recording_id,input_hash,ground_truth_class,ground_truth_status FROM evaluation_samples WHERE dataset_id=? ORDER BY id",
        (dataset_id,),
    ).fetchall()
    return {"dataset_id": dataset_id, "samples": [dict(row) for row in rows]}


def create_dataset(conn: Any, key: str, name: str, description: str = "") -> int:
    previous = conn.execute("SELECT MAX(version) FROM evaluation_datasets WHERE dataset_key=?", (key,)).fetchone()[0]
    version = int(previous or 0) + 1
    fingerprint = hashlib.sha256(f"{key}:{version}".encode()).hexdigest()
    cur = conn.execute(
        "INSERT INTO evaluation_datasets(dataset_key,version,name,description,fingerprint) VALUES (?,?,?,?,?)",
        (key, version, name, description, fingerprint),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_sample(conn: Any, dataset_id: int, segment_id: int, ground_truth_class: str | None = None,
               status: str = "unresolved", source: str = "", notes: str = "") -> int:
    if status not in GROUND_TRUTH_STATUSES:
        raise ValueError("Ungültiger Ground-Truth-Status")
    dataset = conn.execute("SELECT frozen FROM evaluation_datasets WHERE id=?", (dataset_id,)).fetchone()
    if dataset is None:
        raise ValueError("Evaluation-Dataset nicht gefunden")
    if dataset[0]:
        raise ValueError("Eingefrorenes Evaluation-Dataset ist unveränderlich")
    row = conn.execute(
        "SELECT s.recording_id,r.audio_path FROM segments s JOIN recordings r ON r.id=s.recording_id WHERE s.id=?",
        (segment_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Segment nicht gefunden")
    digest = input_hash(row[1])
    try:
        cur = conn.execute(
            "INSERT INTO evaluation_samples(dataset_id,segment_id,recording_id,input_hash,ground_truth_class,ground_truth_status,ground_truth_source,reviewed_at,notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (dataset_id, segment_id, row[0], digest, ground_truth_class, status, source,
             datetime.now(UTC).isoformat() if status == "confirmed" else None, notes),
        )
    except Exception as exc:
        raise ValueError("Doppeltes Evaluation-Sample oder identischer Input") from exc
    conn.commit()
    return int(cur.lastrowid)


def freeze_dataset(conn: Any, dataset_id: int) -> str:
    row = conn.execute("SELECT frozen FROM evaluation_datasets WHERE id=?", (dataset_id,)).fetchone()
    if row is None:
        raise ValueError("Evaluation-Dataset nicht gefunden")
    manifest = _manifest(conn, dataset_id)
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    conn.execute("UPDATE evaluation_datasets SET frozen=1,status='frozen',manifest_json=?,fingerprint=? WHERE id=?",
                 (json.dumps(manifest, sort_keys=True), fingerprint, dataset_id))
    conn.commit()
    return fingerprint


def _contamination(conn: Any, dataset_id: int, artifact: dict[str, Any]) -> list[str]:
    assignments = artifact.get("split", {}).get("recording_assignments", {})
    train_recordings = {int(key) for key, value in assignments.items() if value == "train"}
    split = artifact.get("split", {})
    train_segments = {int(value) for value in split.get("train_segment_ids", [])}
    train_hashes = set(split.get("train_input_hashes", []))
    rows = conn.execute("SELECT segment_id,recording_id,input_hash FROM evaluation_samples WHERE dataset_id=?", (dataset_id,)).fetchall()
    reasons: list[str] = []
    for row in rows:
        if row[1] in train_recordings:
            reasons.append(f"recording:{row[1]}")
        if row[0] in train_segments:
            reasons.append(f"sample:{row[0]}")
        if row[2] in train_hashes:
            reasons.append(f"input_hash:{row[2]}")
    return sorted(set(reasons))


def metrics(y_true: list[str], y_pred: list[str], classes: list[str]) -> dict[str, Any]:
    if not y_true:
        return {"samples": 0, "warning": "Keine bestätigten Ground-Truth-Samples"}
    result: dict[str, Any] = {"samples": len(y_true), "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred))}
    for average in ("macro", "weighted", "micro"):
        p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=classes, average=average, zero_division=0)
        result[f"{average}_precision"], result[f"{average}_recall"], result[f"{average}_f1"] = float(p), float(r), float(f)
    matrix = confusion_matrix(y_true, y_pred, labels=classes).tolist()
    report = classification_report(y_true, y_pred, labels=classes, output_dict=True, zero_division=0)
    result["classes"], result["confusion_matrix"], result["per_class"] = classes, matrix, report
    result["support_warnings"] = [name for name in classes if report.get(name, {}).get("support", 0) < 5]
    return result


def evaluate_model(conn: Any, model_id: int, dataset_id: int, report_path: str | Path | None = None) -> int:
    model = conn.execute("SELECT * FROM model_registry WHERE id=?", (model_id,)).fetchone()
    dataset = conn.execute("SELECT * FROM evaluation_datasets WHERE id=?", (dataset_id,)).fetchone()
    if model is None or dataset is None or not dataset["frozen"]:
        raise ValueError("Modell oder eingefrorenes Evaluation-Dataset fehlt")
    artifact = load_model(model["artifact_path"])
    run = conn.execute("INSERT INTO evaluation_runs(model_id,dataset_id,model_version,pipeline_fingerprint,status,started_at) VALUES (?,?,?,?,?,?)",
                       (model_id, dataset_id, model["artifact_version"], model["pipeline_fingerprint"], "running", datetime.now(UTC).isoformat()))
    run_id = int(run.lastrowid); conn.commit()
    contamination = _contamination(conn, dataset_id, artifact)
    rows = conn.execute("SELECT es.*,r.audio_path,s.start_seconds,s.end_seconds FROM evaluation_samples es JOIN recordings r ON r.id=es.recording_id JOIN segments s ON s.id=es.segment_id WHERE es.dataset_id=? ORDER BY es.id", (dataset_id,)).fetchall()
    y_true: list[str] = []; y_pred: list[str] = []; classes = [str(x) for x in artifact["classes"]]
    for row in rows:
        if row["ground_truth_status"] != "confirmed" or not row["ground_truth_class"]:
            conn.execute("INSERT INTO evaluation_predictions(run_id,sample_id,evaluation_status) VALUES (?,?,?)", (run_id, row["id"], "excluded")); continue
        try:
            audio, rate = sf.read(row["audio_path"], always_2d=True)
            start, end = round(row["start_seconds"] * rate), round(row["end_seconds"] * rate)
            features = extract_features(audio[max(0, start):min(len(audio), end)], int(rate), FeaturePipelineConfig(**artifact["pipeline_config"]))
            begin = time.perf_counter(); probabilities = artifact["estimator"].predict_proba([features.values])[0]; elapsed = (time.perf_counter() - begin) * 1000
            index = int(np.argmax(probabilities)); predicted = str(artifact["estimator"].classes_[index]); confidence = float(probabilities[index])
            conn.execute("INSERT INTO evaluation_predictions(run_id,sample_id,predicted_class,confidence,inference_time_ms) VALUES (?,?,?,?,?)", (run_id, row["id"], predicted, confidence, elapsed))
            y_true.append(row["ground_truth_class"]); y_pred.append(predicted)
        except Exception as exc:
            conn.execute("INSERT INTO evaluation_predictions(run_id,sample_id,evaluation_status,error_message) VALUES (?,?,?,?)", (run_id, row["id"], "error", str(exc)))
    result = metrics(y_true, y_pred, classes); result["contamination_reasons"] = contamination
    status = "contaminated" if contamination else "completed"
    conn.execute("UPDATE evaluation_runs SET status=?,finished_at=?,sample_count=?,evaluated_count=?,excluded_count=?,error_count=?,contamination_status=?,metrics_json=?,report_json=? WHERE id=?",
                 (status, datetime.now(UTC).isoformat(), len(rows), len(y_true), len(rows)-len(y_true), 0, "contaminated" if contamination else "clean", json.dumps(result), json.dumps(result), run_id))
    conn.commit()
    if report_path:
        Path(report_path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_id
"""Reproducible, production-independent evaluation foundation."""

# SQL statements and compact persistence code intentionally mirror the local schema.
# ruff: noqa: E501, E702
