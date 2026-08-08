from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import soundfile as sf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from eventmonitor.dataset import split_by_recording
from eventmonitor.features import FeaturePipelineConfig, extract_features

BASELINE_MODEL_VERSION = "1.0.0"


def build_labeled_dataset(
    conn: Any, config: FeaturePipelineConfig | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[str, ...]]:
    config = config or FeaturePipelineConfig()
    rows = conn.execute(
        """
        SELECT s.id, s.recording_id, s.start_seconds, s.end_seconds, s.label, r.audio_path
        FROM segments s JOIN recordings r ON r.id=s.recording_id
        WHERE s.label IS NOT NULL ORDER BY s.id
        """
    ).fetchall()
    if not rows:
        raise ValueError("Es sind noch keine bestätigten Segmente vorhanden.")
    vectors: list[np.ndarray] = []
    feature_names: tuple[str, ...] | None = None
    for row in rows:
        audio, sample_rate = sf.read(row["audio_path"], always_2d=True)
        excerpt = audio[
            max(0, round(float(row["start_seconds"]) * sample_rate)) : min(
                len(audio), round(float(row["end_seconds"]) * sample_rate)
            )
        ]
        extracted = extract_features(excerpt, int(sample_rate), config)
        vectors.append(extracted.values)
        feature_names = extracted.names
    return (
        np.vstack(vectors),
        np.asarray([row["label"] for row in rows]),
        np.asarray([row["recording_id"] for row in rows], dtype=np.int64),
        np.asarray([row["id"] for row in rows], dtype=np.int64),
        feature_names or (),
    )


def _metrics(estimator: Pipeline, features: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    predicted = estimator.predict(features)
    classes = [str(value) for value in estimator.classes_]
    return {
        "samples": int(len(labels)),
        "accuracy": float(accuracy_score(labels, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
        "macro_f1": float(f1_score(labels, predicted, average="macro", zero_division=0)),
        "classes": classes,
        "confusion_matrix": confusion_matrix(labels, predicted, labels=classes).tolist(),
        "per_class": classification_report(
            labels, predicted, labels=classes, output_dict=True, zero_division=0
        ),
    }


def train_baseline(
    features: np.ndarray,
    labels: np.ndarray,
    recording_ids: np.ndarray,
    feature_names: tuple[str, ...],
    config: FeaturePipelineConfig | None = None,
    *,
    seed: int = 42,
) -> dict[str, Any]:
    config = config or FeaturePipelineConfig()
    features = np.asarray(features, dtype=np.float32)
    labels = np.asarray(labels)
    recording_ids = np.asarray(recording_ids)
    if features.ndim != 2 or len(features) != len(labels) or len(labels) != len(recording_ids):
        raise ValueError("Features, Labels und Aufnahme-IDs müssen zeilenweise zusammenpassen.")
    if features.shape[1] != len(feature_names):
        raise ValueError("Feature-Vektor und Merkmalsnamen passen nicht zusammen.")
    if len(set(labels)) < 2:
        raise ValueError("Für ein Modell werden mindestens zwei bestätigte Klassen benötigt.")
    split = split_by_recording(
        recording_ids,
        labels,
        pipeline_fingerprint=config.fingerprint,
        seed=seed,
    )
    train_indices = split.indices(recording_ids, "train")
    if len(set(labels[train_indices])) < 2:
        raise ValueError("Der Trainingssplit enthält weniger als zwei Klassen.")
    estimator = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(class_weight="balanced", max_iter=2_000, random_state=seed),
            ),
        ]
    )
    estimator.fit(features[train_indices], labels[train_indices])
    metrics = {
        name: _metrics(
            estimator,
            features[split.indices(recording_ids, name)],
            labels[split.indices(recording_ids, name)],
        )
        for name in ("validation", "test")
    }
    return {
        "artifact_version": BASELINE_MODEL_VERSION,
        "trained_at": datetime.now(UTC).isoformat(),
        "pipeline_config": asdict(config),
        "pipeline_fingerprint": config.fingerprint,
        "feature_names": list(feature_names),
        "classes": [str(value) for value in estimator.classes_],
        "split": asdict(split),
        "metrics": metrics,
        "estimator": estimator,
    }


def save_model(artifact: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, destination)
    return destination


def load_model(path: str | Path) -> dict[str, Any]:
    artifact = joblib.load(path)
    if artifact.get("artifact_version") != BASELINE_MODEL_VERSION:
        raise ValueError("Nicht unterstützte Basismodell-Version.")
    config = FeaturePipelineConfig(**artifact["pipeline_config"])
    if artifact.get("pipeline_fingerprint") != config.fingerprint:
        raise ValueError("Feature-Pipeline und Modell-Fingerprint stimmen nicht überein.")
    feature_names = list(artifact.get("feature_names", []))
    if (
        not feature_names
        or len(feature_names) != len(set(feature_names))
        or artifact["estimator"].n_features_in_ != len(feature_names)
    ):
        raise ValueError("Ungültige Merkmalsdefinition im Modell.")
    return artifact
