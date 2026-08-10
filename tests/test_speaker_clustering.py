import math
import wave
from pathlib import Path

import numpy as np
import pytest
from app.database.base import Base
from app.models.dashboard import AudioClip, EventSpeakerCluster, SpeakerCluster
from app.models.event import Event
from app.services.speaker_clustering import cluster_existing_voice_clips, voiceprint
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _wav(path: Path, frequency: float) -> None:
    samples = np.asarray(
        [math.sin(2 * math.pi * frequency * index / 16_000) * 12_000 for index in range(32_000)],
        dtype="<i2",
    )
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(samples.tobytes())


def test_voiceprint_is_normalized(tmp_path: Path) -> None:
    path = tmp_path / "voice.wav"
    _wav(path, 220)
    vector = voiceprint(str(path))
    assert len(vector) == 48
    assert np.linalg.norm(vector) == pytest.approx(1.0)


def test_existing_voice_clips_are_grouped_without_named_person(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _wav(first, 220)
    _wav(second, 220)
    with Session(engine) as db:
        events = [
            Event(
                timestamp=f"2026-08-10T10:00:0{index}",
                event_type="sound",
                label="Speech",
                label_de="Sprache",
                category="VOICE",
                confidence=0.9,
                db_level=60,
                device="mic",
            )
            for index in range(2)
        ]
        db.add_all(events)
        db.flush()
        db.add_all(
            [
                AudioClip(
                    device_id="mic",
                    trigger_id=f"t{index}",
                    received_at=event.timestamp,
                    sha256=str(index) * 64,
                    path=str(path),
                    frame_count=32_000,
                    sample_rate=16_000,
                    event_id=event.id,
                )
                for index, (event, path) in enumerate(
                    zip(events, (first, second), strict=True), start=1
                )
            ]
        )
        db.commit()
        result = cluster_existing_voice_clips(db)
        clusters = list(db.scalars(select(SpeakerCluster)))
        assignments = list(db.scalars(select(EventSpeakerCluster)))
        assert result["analyzed"] == 2
        assert len(clusters) == 1
        assert clusters[0].name == "Person 1"
        assert len(assignments) == 2
