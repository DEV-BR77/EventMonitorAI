import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.api.dashboard import statistics
from app.database.base import Base
from app.models.event import Event
from app.services.audio import LiveAudioHub
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_keeps_session_on_partial_loading_failures() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "Promise.allSettled" in javascript
    assert "if (error?.status === 401) logout();" in javascript
    assert "requestToken === state.token" in javascript


def test_postgres_pool_supports_parallel_dashboard_requests() -> None:
    session_module = (ROOT / "backend" / "app" / "database" / "session.py").read_text(
        encoding="utf-8"
    )

    assert '"pool_size": 20' in session_module
    assert '"pool_pre_ping": True' in session_module


def test_dashboard_statistics_handles_twenty_thousand_events_under_five_seconds() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.bulk_save_objects(
            [
                Event(
                    timestamp=(now - timedelta(seconds=index)).isoformat(),
                    end_timestamp=(now - timedelta(seconds=index)).isoformat(),
                    event_type="AUDIO",
                    label="Speech",
                    label_de="Sprache",
                    category="VOICE",
                    confidence=0.8,
                    db_level=50 + index % 20,
                    avg_db_level=48 + index % 20,
                    device=f"mic-{index % 2}",
                )
                for index in range(20_000)
            ]
        )
        db.commit()
        started = time.perf_counter()
        result = statistics(db, SimpleNamespace(), 1)
        elapsed = time.perf_counter() - started

    assert result["total"] == 20_000
    assert elapsed < 5.0


def test_live_audio_ring_buffer_stays_bounded_during_soak_simulation() -> None:
    hub = LiveAudioHub()
    chunk = b"\x01\x00" * 1_600

    async def simulate_hour() -> None:
        for _ in range(36_000):
            await hub.broadcast("mic", chunk)

    asyncio.run(simulate_hour())

    snapshot = hub.wav_snapshot("mic")
    assert snapshot is not None
    assert len(snapshot) == 160_044
