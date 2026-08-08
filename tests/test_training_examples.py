import hashlib
import io
import sys
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.api.events import training_examples
from app.core.config import settings
from app.database.base import Base
from app.models.dashboard import User
from app.models.event import Event
from app.services.clips import associate_nearest_clip, store_training_clip
from app.services.taxonomy import seed_event_classes
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.insert(0, str(AUDIO_LAB_DIR))

from eventmonitor.db import connect  # noqa: E402
from eventmonitor.live_training import import_live_training_example  # noqa: E402


def _wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000 * 5)
    return output.getvalue()


def test_confirmed_live_clip_becomes_downloadable_training_example(
    tmp_path: Path,
) -> None:
    original_directory = settings.clip_directory
    settings.clip_directory = str(tmp_path / "clips")
    try:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed_event_classes(db)
            now = datetime.now(UTC)
            event = Event(
                timestamp=now.isoformat(),
                event_type="AUDIO",
                label="Knock",
                label_de="Klopfen",
                category="IMPACT",
                confidence=0.91,
                db_level=67,
                device="mic",
                primary_class_code="IMPACT",
                subclass_code="BALL_METAL",
                classification_status="manual",
                corrected_by="operator",
            )
            user = User(username="operator", password_hash="x", role="operator")
            db.add_all([event, user])
            db.commit()
            clip = store_training_clip(
                db,
                _wav(),
                device_id="mic",
                trigger_id="1",
                trigger_uptime_ms=100,
                received_at=(now + timedelta(seconds=3)).isoformat(),
            )

            assert associate_nearest_clip(db, event) == clip
            db.commit()
            examples = training_examples(db, user)

            assert len(examples) == 1
            assert examples[0].subclass_code == "BALL_METAL"
            assert examples[0].label == "Fußball gegen Metall"
            assert examples[0].clip_sha256 == hashlib.sha256(_wav()).hexdigest()
    finally:
        settings.clip_directory = original_directory


def test_audiolab_imports_verified_live_example_once(tmp_path: Path) -> None:
    payload = _wav()
    digest = hashlib.sha256(payload).hexdigest()
    example = {
        "event_id": 42,
        "device_id": "mic",
        "timestamp": datetime.now(UTC).isoformat(),
        "primary_class_code": "IMPACT",
        "subclass_code": "BALL_METAL",
        "label": "Fußball gegen Metall",
        "confidence": 0.91,
        "clip_sha256": digest,
    }
    conn = connect(tmp_path / "audiolab.sqlite3")

    assert import_live_training_example(conn, tmp_path / "library", example, payload)
    assert not import_live_training_example(conn, tmp_path / "library", example, payload)
    row = conn.execute(
        "SELECT label,base_class_code,fine_class_code,assignment_status FROM segments"
    ).fetchone()
    assert tuple(row) == ("Fußball gegen Metall", "IMPACT", "BALL_METAL", "manual")
