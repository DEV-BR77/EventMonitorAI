from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import soundfile as sf

from eventmonitor.features import FeaturePipelineConfig, extract_features


def active_learning_scores(
    artifact: dict[str, Any], features: np.ndarray, uncertainty_weight: float = 0.75
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not 0 <= uncertainty_weight <= 1:
        raise ValueError("Das Unsicherheitsgewicht muss zwischen 0 und 1 liegen.")
    features = np.asarray(features, dtype=np.float32)
    probabilities = artifact["estimator"].predict_proba(features)
    class_count = probabilities.shape[1]
    if class_count < 2:
        raise ValueError("Active Learning benötigt mindestens zwei Modellklassen.")
    safe = np.clip(probabilities, 1e-12, 1.0)
    uncertainty = -np.sum(safe * np.log(safe), axis=1) / np.log(class_count)
    scaler = getattr(artifact["estimator"], "named_steps", {}).get("scale")
    transformed = scaler.transform(features) if scaler is not None else features
    distance = np.linalg.norm(transformed, axis=1)
    low, high = float(np.min(distance)), float(np.max(distance))
    informativeness = (
        (distance - low) / (high - low) if high - low > 1e-12 else np.zeros_like(distance)
    )
    combined = uncertainty_weight * uncertainty + (1 - uncertainty_weight) * informativeness
    return uncertainty, informativeness, combined


def predict_feature_matrix(
    artifact: dict[str, Any], features: np.ndarray, feature_names: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    if list(feature_names) != list(artifact["feature_names"]):
        raise ValueError("Die Merkmalsreihenfolge passt nicht zum Modell.")
    probabilities = artifact["estimator"].predict_proba(np.asarray(features, dtype=np.float32))
    best = np.argmax(probabilities, axis=1)
    classes = np.asarray(artifact["estimator"].classes_)
    return classes[best], probabilities[np.arange(len(best)), best]


def generate_segment_predictions(conn: Any, artifact: dict[str, Any], model_name: str) -> int:
    rows = conn.execute(
        """
        SELECT s.id, s.start_seconds, s.end_seconds, r.audio_path
        FROM segments s JOIN recordings r ON r.id=s.recording_id
        WHERE s.label IS NULL ORDER BY s.id
        """
    ).fetchall()
    if not rows:
        return 0
    config = FeaturePipelineConfig(**artifact["pipeline_config"])
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
    feature_matrix = np.vstack(vectors)
    labels, confidences = predict_feature_matrix(artifact, feature_matrix, feature_names or ())
    uncertainties, informativeness, active_scores = active_learning_scores(artifact, feature_matrix)
    now = datetime.now(UTC).isoformat()
    for row, label, confidence, uncertainty, information, active_score in zip(
        rows,
        labels,
        confidences,
        uncertainties,
        informativeness,
        active_scores,
        strict=True,
    ):
        conn.execute(
            "DELETE FROM predictions WHERE segment_id=? AND model_name=? AND reviewed_at IS NULL",
            (row["id"], model_name),
        )
        conn.execute(
            """
            INSERT INTO predictions(
                segment_id,model_name,predicted_label,confidence,created_at,
                uncertainty_score,informativeness_score,active_learning_score
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                row["id"],
                model_name,
                str(label),
                float(confidence),
                now,
                float(uncertainty),
                float(information),
                float(active_score),
            ),
        )
    conn.commit()
    return len(rows)


def latest_prediction(conn: Any, segment_id: int) -> Any | None:
    return conn.execute(
        "SELECT * FROM predictions WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        (segment_id,),
    ).fetchone()


def record_prediction_review(conn: Any, prediction_id: int, selected_label: str) -> None:
    prediction = conn.execute(
        "SELECT predicted_label FROM predictions WHERE id=?", (prediction_id,)
    ).fetchone()
    if prediction is None:
        raise ValueError("Der Modellvorschlag wurde nicht gefunden.")
    conn.execute(
        """
        UPDATE predictions SET reviewed_at=?,reviewed_label=?,was_correct=? WHERE id=?
        """,
        (
            datetime.now(UTC).isoformat(),
            selected_label,
            int(prediction[0] == selected_label),
            prediction_id,
        ),
    )
    conn.commit()
