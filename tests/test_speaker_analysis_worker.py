import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dashboard import create_speaker_analysis_run, latest_speaker_analysis_run
from app.database.base import Base
from app.models.dashboard import AudioClip, EventSpeakerCluster, SpeakerAnalysisRun, SpeakerCluster, User
from app.models.event import Event
from app.services import speaker_worker


def test_speaker_image_contains_application_version() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile.speaker").read_text(encoding="utf-8")

    assert "COPY VERSION ./VERSION" in dockerfile


def test_speaker_service_receives_required_auth_secret() -> None:
    compose = (Path(__file__).parents[1] / "compose.yaml").read_text(encoding="utf-8")
    worker_service = compose.split("  speaker-worker:", 1)[1].split("  backup:", 1)[0]

    assert "AUTH_SECRET: ${AUTH_SECRET:?Set AUTH_SECRET in .env.docker}" in worker_service
    assert "INGEST_API_KEY: ${INGEST_API_KEY:?Set INGEST_API_KEY in .env.docker}" in worker_service


def test_compose_configuration_is_valid() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")
    environment = os.environ | {
        "AUTH_SECRET": "test-auth-secret-with-at-least-32-characters",
        "INGEST_API_KEY": "test-ingest-api-key",
        "POSTGRES_PASSWORD": "test-postgres-password",
    }

    subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=True,
    )


def test_analysis_run_is_queued_and_duplicate_is_rejected() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.info["tenant_id"] = 1
        user = User(username="admin", password_hash="x", role="admin")
        run = create_speaker_analysis_run(db, user)
        assert run.status == "pending"
        assert latest_speaker_analysis_run(db, user).id == run.id
        with pytest.raises(HTTPException) as error:
            create_speaker_analysis_run(db, user)
        assert error.value.status_code == 409


def test_worker_reports_progress_and_separates_embeddings(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(speaker_worker, "SessionLocal", factory)
    vectors = {
        "a.wav": np.asarray([1.0, 0.0], dtype=np.float32),
        "b.wav": np.asarray([0.99, 0.01], dtype=np.float32),
        "c.wav": np.asarray([0.0, 1.0], dtype=np.float32),
    }
    monkeypatch.setattr(speaker_worker, "_embedding", lambda _encoder, path: vectors[path])
    with factory() as db:
        db.info["tenant_id"] = 1
        events = [Event(timestamp=f"2026-08-11T12:00:0{i}", event_type="sound", label="Speech", label_de="Sprache", category="VOICE", confidence=.8, db_level=50, device="mic") for i in range(3)]
        db.add_all(events)
        db.flush()
        db.add_all(AudioClip(device_id="mic", trigger_id=str(i), received_at=event.timestamp, sha256=str(i).zfill(64), path=name, frame_count=16000, sample_rate=16000, event_id=event.id) for i, (event, name) in enumerate(zip(events, vectors, strict=True), 1))
        run = SpeakerAnalysisRun(status="pending", requested_by="admin")
        db.add(run)
        db.commit()
        run_id = run.id

    assert speaker_worker.process_run(run_id, SimpleNamespace()) is not None
    with factory() as db:
        run = db.get(SpeakerAnalysisRun, run_id)
        assert (run.status, run.processed, run.total, run.clustered, run.skipped) == ("completed", 3, 3, 2, 0)
        assert len(list(db.scalars(select(SpeakerCluster)))) == 2
        assert len(list(db.scalars(select(EventSpeakerCluster)))) == 3


def test_frontend_exposes_visible_worker_progress() -> None:
    javascript = open("frontend/app.js", encoding="utf-8").read()
    markup = open("frontend/index.html", encoding="utf-8").read()
    assert "/api/speaker-analysis/runs/latest" in javascript
    assert "speaker-progress-bar" in markup
    assert "Dashboard und Mikrofoneingang arbeiten währenddessen normal weiter" in markup
