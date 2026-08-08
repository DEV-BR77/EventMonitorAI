import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

import eventmonitor.inference as inference  # noqa: E402
from eventmonitor.db import connect  # noqa: E402
from eventmonitor.features import FeaturePipelineConfig  # noqa: E402
from eventmonitor.inference import (  # noqa: E402
    generate_segment_predictions,
    latest_prediction,
    predict_feature_matrix,
    record_prediction_review,
)


def test_prediction_uses_model_probabilities_and_feature_order() -> None:
    estimator = LogisticRegression().fit(
        [[0, 1], [1, 0], [0.1, 0.9], [0.9, 0.1]], ["B", "A", "B", "A"]
    )
    artifact = {"estimator": estimator, "feature_names": ["one", "two"]}
    labels, confidence = predict_feature_matrix(
        artifact, np.asarray([[0.95, 0.05]]), ("one", "two")
    )
    assert labels.tolist() == ["A"]
    assert 0.5 < confidence[0] <= 1
    with pytest.raises(ValueError, match="Merkmalsreihenfolge"):
        predict_feature_matrix(artifact, np.asarray([[1, 0]]), ("two", "one"))


def test_prediction_review_records_confirmation_and_correction(tmp_path: Path) -> None:
    conn = connect(tmp_path / "review.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path) VALUES ('x','h','x.wav')"
    )
    conn.execute("INSERT INTO segments(recording_id,start_seconds,end_seconds) VALUES (1,0,1)")
    conn.execute(
        "INSERT INTO predictions(segment_id,model_name,predicted_label,confidence) "
        "VALUES (1,'baseline','Hupe',0.8)"
    )
    conn.commit()
    prediction = latest_prediction(conn, 1)
    record_prediction_review(conn, prediction["id"], "Hund")
    reviewed = latest_prediction(conn, 1)
    assert reviewed["reviewed_label"] == "Hund"
    assert reviewed["was_correct"] == 0
    assert reviewed["reviewed_at"]
    conn.close()


def test_generation_replaces_unreviewed_proposal_for_same_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "generation.sqlite3")
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path) VALUES ('x','h','x.wav')"
    )
    conn.execute("INSERT INTO segments(recording_id,start_seconds,end_seconds) VALUES (1,0,1)")
    conn.commit()
    estimator = LogisticRegression().fit([[0, 1], [1, 0]], ["Hund", "Hupe"])
    config = FeaturePipelineConfig(n_mels=16)
    artifact = {
        "estimator": estimator,
        "feature_names": ["one", "two"],
        "pipeline_config": asdict(config),
    }
    monkeypatch.setattr(inference.sf, "read", lambda *args, **kwargs: (np.ones((10, 1)), 10))
    monkeypatch.setattr(
        inference,
        "extract_features",
        lambda *args, **kwargs: SimpleNamespace(
            values=np.asarray([1.0, 0.0]), names=("one", "two")
        ),
    )
    assert generate_segment_predictions(conn, artifact, "baseline") == 1
    assert generate_segment_predictions(conn, artifact, "baseline") == 1
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 1
    assert latest_prediction(conn, 1)["predicted_label"] == "Hupe"
    conn.close()
