import sys
from pathlib import Path

import numpy as np
import pytest

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.dataset import DatasetSplit, split_by_recording  # noqa: E402


def test_split_keeps_recordings_isolated_and_covers_all_segments() -> None:
    recording_ids = np.repeat(np.arange(1, 11), [3, 2, 4, 1, 2, 3, 2, 1, 4, 2])
    labels = ["Hupe" if index % 2 else "Hund" for index in range(len(recording_ids))]
    split = split_by_recording(recording_ids, labels, pipeline_fingerprint="features-v1")
    index_sets = {name: set(split.indices(recording_ids, name)) for name in split.segment_counts}
    assert set.union(*index_sets.values()) == set(range(len(recording_ids)))
    assert not (index_sets["train"] & index_sets["validation"])
    assert not (index_sets["train"] & index_sets["test"])
    for recording_id in set(recording_ids):
        assigned = {
            name
            for name, indices in index_sets.items()
            if any(recording_ids[index] == recording_id for index in indices)
        }
        assert len(assigned) == 1


def test_split_is_reproducible_and_manifest_round_trips(tmp_path: Path) -> None:
    recording_ids = list(range(1, 9))
    labels = ["A", "A", "B", "B", "A", "B", "A", "B"]
    first = split_by_recording(recording_ids, labels, pipeline_fingerprint="abc", seed=7)
    second = split_by_recording(recording_ids, labels, pipeline_fingerprint="abc", seed=7)
    assert first == second
    loaded = DatasetSplit.load(first.save(tmp_path / "split.json"))
    assert loaded == first
    assert set(first.recording_assignments.values()) == {"train", "validation", "test"}


def test_split_rejects_too_few_recordings() -> None:
    with pytest.raises(ValueError, match="mindestens drei"):
        split_by_recording([1, 1, 2], ["A", "B", "A"], pipeline_fingerprint="abc")
