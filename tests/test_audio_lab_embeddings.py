import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.db import connect  # noqa: E402
from eventmonitor.embeddings import (  # noqa: E402
    embedding_from_features,
    similar_segments,
    store_embeddings,
)


def test_embeddings_are_normalized_after_training_scaler() -> None:
    scaler = StandardScaler().fit([[0, 0], [2, 4], [4, 8]])
    artifact = {"estimator": Pipeline([("scale", scaler)])}
    embeddings = embedding_from_features(artifact, np.asarray([[4, 8], [1, 2]]))
    assert embeddings.dtype == np.dtype("float32")
    assert np.linalg.norm(embeddings, axis=1) == pytest.approx([1, 1])


def test_similarity_search_returns_nearest_segment_first(tmp_path: Path) -> None:
    conn = connect(tmp_path / "embeddings.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path) VALUES ('x','h','x.wav')"
    )
    for start, label in ((0, "A"), (1, "A"), (2, "B")):
        conn.execute(
            "INSERT INTO segments(recording_id,start_seconds,end_seconds,label) VALUES (1,?,?,?)",
            (start, start + 1, label),
        )
    conn.commit()
    vectors = np.asarray([[1, 0], [0.9, 0.1], [-1, 0]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    assert store_embeddings(conn, np.asarray([1, 2, 3]), vectors, "model", "pipeline") == 3
    results = similar_segments(conn, 1)
    assert [row["segment_id"] for row in results] == [2, 3]
    assert results[0]["similarity"] > 0.99
    assert results[1]["similarity"] == pytest.approx(-1)
    conn.close()
