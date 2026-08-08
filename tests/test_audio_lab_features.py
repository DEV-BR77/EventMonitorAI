import sys
from pathlib import Path

import numpy as np
import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.features import (  # noqa: E402
    FEATURE_PIPELINE_VERSION,
    FeaturePipelineConfig,
    extract_features,
    preprocess_audio,
)


def test_preprocessing_is_mono_resampled_and_fixed_length() -> None:
    config = FeaturePipelineConfig(clip_duration_seconds=1.0)
    stereo = np.column_stack((np.ones(8_000), np.zeros(8_000)))
    processed = preprocess_audio(stereo, 8_000, config)
    assert processed.shape == (16_000,)
    assert processed.dtype == np.float32
    assert np.max(np.abs(processed)) == pytest.approx(1.0)


def test_feature_vector_is_stable_and_self_describing() -> None:
    config = FeaturePipelineConfig(clip_duration_seconds=1.0, n_mels=16)
    time = np.arange(16_000) / 16_000
    signal = np.sin(2 * np.pi * 1_000 * time).astype(np.float32)
    first = extract_features(signal, 16_000, config)
    second = extract_features(signal, 16_000, config)
    assert first.pipeline_version == FEATURE_PIPELINE_VERSION
    assert first.values.shape == (44,)
    assert len(first.names) == len(set(first.names)) == 44
    assert np.array_equal(first.values, second.values)
    assert first.metadata()["pipeline_fingerprint"] == config.fingerprint


def test_pipeline_config_round_trip_and_fingerprint(tmp_path: Path) -> None:
    config = FeaturePipelineConfig(n_mels=32)
    loaded = FeaturePipelineConfig.load(config.save(tmp_path / "pipeline.json"))
    assert loaded == config
    assert loaded.fingerprint == config.fingerprint
    assert FeaturePipelineConfig(n_mels=48).fingerprint != config.fingerprint


def test_unknown_pipeline_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="Nicht unterstützte"):
        FeaturePipelineConfig(version="99.0.0")
