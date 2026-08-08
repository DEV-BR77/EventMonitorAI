from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import soundfile as sf

from eventmonitor.features import FeaturePipelineConfig, extract_features


def embedding_from_features(artifact: dict[str, Any], features: np.ndarray) -> np.ndarray:
    features = np.asarray(features, dtype=np.float32)
    if features.ndim != 2:
        raise ValueError("Features für Embeddings müssen eine Matrix sein.")
    scaler = getattr(artifact["estimator"], "named_steps", {}).get("scale")
    transformed = scaler.transform(features) if scaler is not None else features
    norms = np.linalg.norm(transformed, axis=1, keepdims=True)
    normalized = transformed / np.maximum(norms, 1e-12)
    return np.asarray(normalized, dtype="<f4")


def store_embeddings(
    conn: Any,
    segment_ids: np.ndarray,
    vectors: np.ndarray,
    model_name: str,
    pipeline_fingerprint: str,
) -> int:
    vectors = np.asarray(vectors, dtype="<f4")
    if vectors.ndim != 2 or len(segment_ids) != len(vectors):
        raise ValueError("Segment-IDs und Embeddings müssen zeilenweise zusammenpassen.")
    now = datetime.now(UTC).isoformat()
    for segment_id, vector in zip(segment_ids, vectors, strict=True):
        conn.execute(
            """
            INSERT INTO segment_embeddings(
                segment_id,model_name,pipeline_fingerprint,dimension,vector,created_at
            ) VALUES (?,?,?,?,?,?)
            ON CONFLICT(segment_id,model_name) DO UPDATE SET
                pipeline_fingerprint=excluded.pipeline_fingerprint,
                dimension=excluded.dimension,vector=excluded.vector,created_at=excluded.created_at
            """,
            (
                int(segment_id),
                model_name,
                pipeline_fingerprint,
                len(vector),
                vector.tobytes(),
                now,
            ),
        )
    conn.commit()
    return len(vectors)


def generate_segment_embeddings(conn: Any, artifact: dict[str, Any], model_name: str) -> int:
    rows = conn.execute(
        """
        SELECT s.id,s.start_seconds,s.end_seconds,r.audio_path
        FROM segments s JOIN recordings r ON r.id=s.recording_id ORDER BY s.id
        """
    ).fetchall()
    if not rows:
        return 0
    config = FeaturePipelineConfig(**artifact["pipeline_config"])
    vectors: list[np.ndarray] = []
    names: tuple[str, ...] | None = None
    for row in rows:
        audio, sample_rate = sf.read(row["audio_path"], always_2d=True)
        excerpt = audio[
            max(0, round(float(row["start_seconds"]) * sample_rate)) : min(
                len(audio), round(float(row["end_seconds"]) * sample_rate)
            )
        ]
        extracted = extract_features(excerpt, int(sample_rate), config)
        vectors.append(extracted.values)
        names = extracted.names
    if list(names or ()) != list(artifact["feature_names"]):
        raise ValueError("Die Embedding-Features passen nicht zum Modell.")
    embeddings = embedding_from_features(artifact, np.vstack(vectors))
    return store_embeddings(
        conn,
        np.asarray([row["id"] for row in rows]),
        embeddings,
        model_name,
        artifact["pipeline_fingerprint"],
    )


def similar_segments(conn: Any, segment_id: int, limit: int = 10) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    source = conn.execute(
        """
        SELECT * FROM segment_embeddings WHERE segment_id=? ORDER BY created_at DESC LIMIT 1
        """,
        (segment_id,),
    ).fetchone()
    if source is None:
        return []
    source_vector = np.frombuffer(source["vector"], dtype="<f4", count=source["dimension"])
    candidates = conn.execute(
        """
        SELECT e.segment_id,e.dimension,e.vector,s.recording_id,
               s.start_seconds,s.end_seconds,s.label
        FROM segment_embeddings e JOIN segments s ON s.id=e.segment_id
        WHERE e.model_name=? AND e.pipeline_fingerprint=? AND e.segment_id<>?
        """,
        (source["model_name"], source["pipeline_fingerprint"], segment_id),
    ).fetchall()
    results = []
    for row in candidates:
        if row["dimension"] != source["dimension"]:
            continue
        vector = np.frombuffer(row["vector"], dtype="<f4", count=row["dimension"])
        results.append(
            {
                "segment_id": row["segment_id"],
                "recording_id": row["recording_id"],
                "start_seconds": row["start_seconds"],
                "end_seconds": row["end_seconds"],
                "label": row["label"],
                "similarity": float(np.clip(np.dot(source_vector, vector), -1, 1)),
            }
        )
    return sorted(results, key=lambda item: item["similarity"], reverse=True)[:limit]
