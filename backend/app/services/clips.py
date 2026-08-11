import hashlib
import io
import os
import tempfile
import wave
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dashboard import AudioClip
from app.models.event import Event

MAX_CLIP_BYTES = 16_000 * 2 * 10 + 44
BERLIN = ZoneInfo("Europe/Berlin")


def normalized_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BERLIN)
    return parsed.astimezone(UTC)


def validate_training_clip(payload: bytes) -> tuple[int, int]:
    if not payload or len(payload) > MAX_CLIP_BYTES:
        raise ValueError("Clip exceeds maximum size")
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_count = audio.getnframes()
    except (EOFError, wave.Error) as exc:
        raise ValueError("Invalid WAV clip") from exc
    if channels != 1 or sample_width != 2 or sample_rate != 16_000:
        raise ValueError("Clip must be 16-bit mono PCM at 16000 Hz")
    if not 16_000 <= frame_count <= 160_000:
        raise ValueError("Clip must contain between 1 and 10 seconds")
    return sample_rate, frame_count


def store_training_clip(
    db: Session,
    payload: bytes,
    *,
    device_id: str,
    trigger_id: str,
    trigger_uptime_ms: int,
    received_at: str,
) -> AudioClip:
    sample_rate, frame_count = validate_training_clip(payload)
    digest = hashlib.sha256(payload).hexdigest()
    existing = db.scalar(select(AudioClip).where(AudioClip.sha256 == digest))
    if existing is not None:
        return existing
    directory = Path(settings.clip_directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest}.wav"
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".wav.tmp", delete=False) as file:
        temporary = Path(file.name)
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)
    clip = AudioClip(
        device_id=device_id,
        trigger_id=trigger_id,
        trigger_uptime_ms=trigger_uptime_ms,
        received_at=received_at,
        sha256=digest,
        path=str(target),
        frame_count=frame_count,
        sample_rate=sample_rate,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def associate_nearest_clip(
    db: Session, event: Event, max_seconds: float = 20.0
) -> AudioClip | None:
    existing = db.scalars(select(AudioClip).where(AudioClip.event_id == event.id)).first()
    if existing is not None:
        return existing
    candidates = list(
        db.scalars(
            select(AudioClip).where(
                AudioClip.device_id == event.device,
                AudioClip.event_id.is_(None),
            )
        ).all()
    )
    event_time = normalized_utc(event.timestamp)
    distances = [
        (
            abs((normalized_utc(clip.received_at) - event_time).total_seconds()),
            clip,
        )
        for clip in candidates
    ]
    if not distances:
        return None
    distance, clip = min(distances, key=lambda item: item[0])
    if distance > max_seconds:
        return None
    clip.event_id = event.id
    db.flush()
    return clip


def associate_nearest_event(
    db: Session, clip: AudioClip, max_seconds: float = 20.0
) -> Event | None:
    events = list(
        db.scalars(
            select(Event).where(Event.device == clip.device_id).order_by(Event.id.desc())
        ).all()
    )
    linked_event_ids = set(
        db.scalars(select(AudioClip.event_id).where(AudioClip.event_id.is_not(None))).all()
    )
    clip_time = normalized_utc(clip.received_at)
    distances = [
        (
            abs((normalized_utc(event.timestamp) - clip_time).total_seconds()),
            event,
        )
        for event in events
        if event.id not in linked_event_ids
    ]
    if not distances:
        return None
    distance, event = min(distances, key=lambda item: item[0])
    if distance > max_seconds:
        return None
    clip.event_id = event.id
    db.flush()
    return event


def reconcile_clip_links(db: Session) -> int:
    linked = list(db.scalars(select(AudioClip).where(AudioClip.event_id.is_not(None))))
    by_event: dict[int, list[AudioClip]] = {}
    for clip in linked:
        by_event.setdefault(clip.event_id, []).append(clip)
    changed = 0
    for event_id, clips in by_event.items():
        if len(clips) < 2:
            continue
        event = db.get(Event, event_id)
        if event is None:
            continue
        keep = min(
            clips,
            key=lambda clip: abs(
                (normalized_utc(clip.received_at) - normalized_utc(event.timestamp)).total_seconds()
            ),
        )
        for clip in clips:
            if clip is not keep:
                clip.event_id = None
                changed += 1
    db.flush()
    for clip in db.scalars(
        select(AudioClip).where(AudioClip.event_id.is_(None)).order_by(AudioClip.received_at)
    ):
        if associate_nearest_event(db, clip) is not None:
            changed += 1
    db.commit()
    return changed
