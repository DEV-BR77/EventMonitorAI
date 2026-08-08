from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

DATASET_SPLIT_VERSION = "1.0.0"
SPLIT_NAMES = ("train", "validation", "test")


@dataclass(frozen=True)
class DatasetSplit:
    version: str
    seed: int
    ratios: tuple[float, float, float]
    pipeline_fingerprint: str
    recording_assignments: dict[int, str]
    segment_counts: dict[str, int]
    label_counts: dict[str, dict[str, int]]

    def indices(self, recording_ids: Iterable[int], split: str) -> np.ndarray:
        if split not in SPLIT_NAMES:
            raise ValueError(f"Unbekannter Datensatzbereich: {split}")
        return np.asarray(
            [
                index
                for index, recording_id in enumerate(recording_ids)
                if self.recording_assignments[int(recording_id)] == split
            ],
            dtype=np.int64,
        )

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> DatasetSplit:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("version") != DATASET_SPLIT_VERSION:
            raise ValueError("Nicht unterstützte Dataset-Split-Version.")
        payload["ratios"] = tuple(payload["ratios"])
        payload["recording_assignments"] = {
            int(recording_id): split
            for recording_id, split in payload["recording_assignments"].items()
        }
        return cls(**payload)


def _group_counts(group_count: int, ratios: tuple[float, float, float]) -> list[int]:
    counts = [1, 1, 1]
    targets = [ratio * group_count for ratio in ratios]
    for _ in range(group_count - len(SPLIT_NAMES)):
        split_index = max(range(3), key=lambda index: targets[index] - counts[index])
        counts[split_index] += 1
    return counts


def split_by_recording(
    recording_ids: Iterable[int],
    labels: Iterable[str],
    *,
    pipeline_fingerprint: str,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
) -> DatasetSplit:
    recording_ids = [int(value) for value in recording_ids]
    labels = [str(value) for value in labels]
    if len(recording_ids) != len(labels) or not recording_ids:
        raise ValueError("Aufnahme-IDs und Labels müssen gleich lang und nicht leer sein.")
    if len(ratios) != 3 or any(value <= 0 for value in ratios) or not np.isclose(sum(ratios), 1):
        raise ValueError("Die drei positiven Split-Anteile müssen zusammen 1 ergeben.")
    groups = sorted(set(recording_ids))
    if len(groups) < 3:
        raise ValueError(
            "Für Train, Validierung und Test werden mindestens drei Aufnahmen benötigt."
        )

    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    counts = _group_counts(len(groups), ratios)
    assignments: dict[int, str] = {}
    offset = 0
    for split, count in zip(SPLIT_NAMES, counts, strict=True):
        assignments.update({group: split for group in groups[offset : offset + count]})
        offset += count

    segment_counts = {split: 0 for split in SPLIT_NAMES}
    label_counters = {split: Counter() for split in SPLIT_NAMES}
    for recording_id, label in zip(recording_ids, labels, strict=True):
        split = assignments[recording_id]
        segment_counts[split] += 1
        label_counters[split][label] += 1
    return DatasetSplit(
        version=DATASET_SPLIT_VERSION,
        seed=seed,
        ratios=ratios,
        pipeline_fingerprint=pipeline_fingerprint,
        recording_assignments=assignments,
        segment_counts=segment_counts,
        label_counts={split: dict(label_counters[split]) for split in SPLIT_NAMES},
    )
