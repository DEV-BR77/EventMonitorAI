import sys
from pathlib import Path

import numpy as np
import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.features import FeaturePipelineConfig  # noqa: E402
from eventmonitor.training import load_model, save_model, train_baseline  # noqa: E402


def _training_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(4)
    recording_ids = np.repeat(np.arange(1, 10), 4)
    labels = np.tile(["Hupe", "Hupe", "Hund", "Hund"], 9)
    features = np.column_stack(
        (
            (labels == "Hupe").astype(float) + rng.normal(0, 0.05, len(labels)),
            (labels == "Hund").astype(float) + rng.normal(0, 0.05, len(labels)),
        )
    )
    return features, labels, recording_ids


def test_baseline_reports_validation_and_untouched_test_metrics(tmp_path: Path) -> None:
    features, labels, recording_ids = _training_data()
    config = FeaturePipelineConfig(n_mels=16)
    artifact = train_baseline(features, labels, recording_ids, ("horn", "dog"), config, seed=3)
    assert artifact["classes"] == ["Hund", "Hupe"]
    assert artifact["metrics"]["validation"]["macro_f1"] == pytest.approx(1.0)
    assert artifact["metrics"]["test"]["balanced_accuracy"] == pytest.approx(1.0)
    assert artifact["metrics"]["test"]["samples"] > 0
    loaded = load_model(save_model(artifact, tmp_path / "model.joblib"))
    assert loaded["pipeline_fingerprint"] == config.fingerprint
    assert np.array_equal(loaded["estimator"].predict(features[:2]), labels[:2])


def test_baseline_rejects_single_class() -> None:
    with pytest.raises(ValueError, match="mindestens zwei"):
        train_baseline(np.ones((3, 2)), np.asarray(["A"] * 3), np.arange(3), ("a", "b"))


def test_model_rejects_changed_pipeline_fingerprint(tmp_path: Path) -> None:
    features, labels, recording_ids = _training_data()
    artifact = train_baseline(features, labels, recording_ids, ("a", "b"))
    artifact["pipeline_fingerprint"] = "manipulated"
    path = save_model(artifact, tmp_path / "changed.joblib")
    with pytest.raises(ValueError, match="Fingerprint"):
        load_model(path)
