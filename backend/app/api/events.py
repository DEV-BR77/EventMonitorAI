import base64
import csv
import hashlib
import io
import logging
import math
import struct
import time
import wave
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, require_roles
from app.database.session import get_db
from app.models.dashboard import (
    AssessmentConfig,
    AudioClip,
    Device,
    DeviceCredential,
    DeviceLevelSample,
    DeviceTelemetry,
    EventClass,
    EventClassificationRevision,
    EventPersonAssignment,
    IgnoredDetectionPattern,
    PersonProfile,
    ReviewRun,
    User,
)
from app.models.event import Event
from app.schemas.dashboard import (
    DeviceTelemetryRead,
    DeviceTelemetryWrite,
    PersonAssignmentWrite,
)
from app.schemas.event import (
    BulkClassificationUpdate,
    EventClassificationRevisionRead,
    EventClassificationUpdate,
    EventCreate,
    EventRead,
    HistoricalImportRequest,
    HistoricalImportResult,
    ReviewQueueItem,
    ReviewRunCreate,
    ReviewRunRead,
    ReviewSummary,
    TrainingExampleRead,
)
from app.services.audio import live_audio_hub
from app.services.calibration import calibrated_db
from app.services.clips import (
    associate_nearest_clip,
    associate_nearest_event,
    normalized_utc,
    store_training_clip,
)
from app.services.event_aggregation import merge_candidate
from app.services.label_translation import translate_label
from app.services.live import live_hub
from app.services.noise_assessment import assessment_for
from app.services.notifications import trigger_notifications
from app.services.push import send_event_pushes
from app.services.review import process_review_run
from app.services.taxonomy import base_class_for_detection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/events",
    tags=["Events"],
)

_PCM_BYTES_PER_SECOND = 16_000 * 2
_AUDIO_BURST_BYTES = _PCM_BYTES_PER_SECOND * 5
_audio_ingest_buckets: dict[str, tuple[float, float]] = {}


def _accept_realtime_audio(device_id: str, byte_count: int) -> bool:
    """Allow one real-time PCM stream plus a short reconnect burst per device."""
    now = time.monotonic()
    tokens, updated_at = _audio_ingest_buckets.get(
        device_id, (float(_AUDIO_BURST_BYTES), now)
    )
    tokens = min(
        float(_AUDIO_BURST_BYTES),
        tokens + max(0.0, now - updated_at) * _PCM_BYTES_PER_SECOND,
    )
    accepted = tokens >= byte_count
    if accepted:
        tokens -= byte_count
    _audio_ingest_buckets[device_id] = (tokens, now)
    return accepted

DatabaseSession = Annotated[Session, Depends(get_db)]


def verify_ingest_key(
    db: DatabaseSession,
    x_api_key: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_device_secret: Annotated[str | None, Header()] = None,
) -> None:
    if x_device_id and x_device_secret:
        digest = hashlib.sha256(x_device_secret.encode()).hexdigest()
        credential = db.scalar(
            select(DeviceCredential).where(
                DeviceCredential.device_id == x_device_id,
                DeviceCredential.secret_hash == digest,
                DeviceCredential.active.is_(True),
            )
        )
        if credential is None:
            raise HTTPException(status_code=401, detail="Ungültige Gerätezugangsdaten")
        db.info["tenant_id"] = credential.tenant_id
        db.info["authenticated_device_id"] = credential.device_id
        credential.last_used_at = datetime.now(UTC).isoformat()
        return
    if settings.ingest_api_key and x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    db.info["tenant_id"] = 1


def _ensure_ingest_device(db: Session, device_id: str) -> None:
    authenticated = db.info.get("authenticated_device_id")
    if authenticated is not None and authenticated != device_id:
        raise HTTPException(status_code=403, detail="Gerätekennung stimmt nicht mit Zugang überein")


def _normalized_detection_label(label: str) -> str:
    return " ".join(label.casefold().split())[:160]


def _learned_class_for_detection(db: Session, label: str) -> tuple[str, str | None] | None:
    rows = list(
        db.execute(
            select(Event.primary_class_code, Event.subclass_code).where(
                Event.label == label,
                Event.classification_status == "manual",
                Event.primary_class_code.is_not(None),
            )
        ).all()
    )
    if len(rows) < 2:
        return None
    primary_counts: Counter[str] = Counter()
    counts: Counter[tuple[str, str | None]] = Counter()
    for primary, subclass in rows:
        primary_counts[primary] += 1
        counts[(primary, subclass)] += 1
    learned_primary, primary_count = primary_counts.most_common(1)[0]
    required_ratio = 1.0 if len(rows) == 2 else 0.8
    if primary_count / len(rows) < required_ratio:
        return None
    learned, count = max(counts.items(), key=lambda item: item[1])
    if learned[0] == learned_primary and count / primary_count >= required_ratio:
        return learned
    return learned_primary, None


def _is_voice_candidate(label: str, category: str) -> bool:
    normalized = _normalized_detection_label(label)
    return category in {"VOICE", "VOCALIZATION", "HUMAN_SOUND"} or any(
        token in normalized
        for token in ("speech", "voice", "shout", "scream", "crying", "cat", "animal")
    )


def _contextual_class_for_detection(
    db: Session, timestamp: str, label: str, category: str
) -> tuple[str, str | None] | None:
    if not _is_voice_candidate(label, category):
        return None
    try:
        current = normalized_utc(timestamp)
    except ValueError:
        return None
    matches: list[tuple[str, str | None]] = []
    for event in db.scalars(select(Event).order_by(desc(Event.id)).limit(80)):
        if event.classification_status not in {"manual", "learned"}:
            continue
        if event.primary_class_code != "VOICE_LOUD" or event.subclass_code is None:
            continue
        try:
            distance = abs((normalized_utc(event.timestamp) - current).total_seconds())
        except ValueError:
            continue
        if distance <= 12:
            matches.append((event.primary_class_code, event.subclass_code))
    return Counter(matches).most_common(1)[0][0] if matches else None


def _apply_learned_classifications(db: Session, source: Event) -> int:
    changed = 0
    learned = _learned_class_for_detection(db, source.label)
    if learned is not None:
        for event in db.scalars(
            select(Event).where(
                Event.label == source.label,
                Event.classification_status == "automatic",
            )
        ):
            event.primary_class_code, event.subclass_code = learned
            event.classification_status = "suggested"
            event.corrected_by = "Lernvorschlag"
            event.corrected_at = datetime.now(UTC).isoformat()
            changed += 1
    if source.primary_class_code == "VOICE_LOUD" and source.subclass_code:
        source_time = normalized_utc(source.timestamp)
        for event in db.scalars(select(Event).where(Event.classification_status == "automatic")):
            if not _is_voice_candidate(event.label, event.category):
                continue
            try:
                distance = abs((normalized_utc(event.timestamp) - source_time).total_seconds())
            except ValueError:
                continue
            if distance <= 12:
                event.primary_class_code = source.primary_class_code
                event.subclass_code = source.subclass_code
                event.classification_status = "suggested"
                event.corrected_by = "Lernvorschlag (Zeit-/Stimmkontext)"
                event.corrected_at = datetime.now(UTC).isoformat()
                changed += 1
    return changed


@router.post("/audio/{device_id}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_live_audio(
    device_id: str,
    pcm: Annotated[bytes, Body(media_type="application/octet-stream")],
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> dict[str, int]:
    if not pcm or len(pcm) > 64_000 or len(pcm) % 2:
        raise HTTPException(status_code=422, detail="Invalid 16-bit PCM chunk")
    if not _accept_realtime_audio(device_id, len(pcm)):
        # Mit 202 bestätigen, damit ein zu schnell sendendes Gerät keine noch
        # größere Wiederholungswarteschlange aufbaut. Überschüssige PCM-Daten
        # dürfen weder Ringpuffer noch Live-Ausgabe verdrängen.
        return {"bytes": len(pcm), "listeners": 0}
    _ensure_ingest_device(db, device_id)
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Unknown device")
    if not device.enabled:
        raise HTTPException(status_code=409, detail="Device disabled")
    # Keine Datenbankverbindung über die potenziell langsame WebSocket-Ausgabe
    # hinweg belegen. Insbesondere abgebrochene Mobilbrowser dürfen den Pool
    # nicht erschöpfen.
    db.rollback()
    listeners = await live_audio_hub.broadcast(device_id, pcm)
    return {"bytes": len(pcm), "listeners": listeners}


@router.post("/telemetry", response_model=DeviceTelemetryRead)
def update_device_telemetry(
    data: DeviceTelemetryWrite,
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> DeviceTelemetry:
    _ensure_ingest_device(db, data.device_id)
    now = datetime.now(UTC).isoformat()
    telemetry = db.scalar(
        select(DeviceTelemetry).where(DeviceTelemetry.device_id == data.device_id)
    )
    values = data.model_dump()
    values["db_level"] = calibrated_db(db, data.device_id, values["db_level"])
    total = values["packets_received"] + values["packets_lost"]
    values["loss_rate"] = round(values["packets_lost"] / total, 6) if total else 0.0
    values["last_seen"] = now
    if telemetry is None:
        telemetry = DeviceTelemetry(**values)
        db.add(telemetry)
    else:
        for key, value in values.items():
            setattr(telemetry, key, value)

    previous_sample = db.scalar(
        select(DeviceLevelSample)
        .where(DeviceLevelSample.device_id == data.device_id)
        .order_by(desc(DeviceLevelSample.id))
        .limit(1)
    )
    if (
        previous_sample is None
        or (
            datetime.fromisoformat(now) - datetime.fromisoformat(previous_sample.timestamp)
        ).total_seconds()
        >= 5
    ):
        db.add(
            DeviceLevelSample(
                device_id=data.device_id,
                timestamp=now,
                db_level=values["db_level"],
            )
        )
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        db.execute(delete(DeviceLevelSample).where(DeviceLevelSample.timestamp < cutoff))

    device = db.scalar(select(Device).where(Device.device_id == data.device_id))
    if device is None:
        db.add(Device(device_id=data.device_id, name=data.device_id, last_seen=now))
    else:
        device.last_seen = now
    db.commit()
    db.refresh(telemetry)
    return telemetry


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event_data: EventCreate,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
) -> Event:
    _ensure_ingest_device(db, event_data.device)
    label_de, category = translate_label(
        event_data.label,
        event_data.device,
    )

    event_values = event_data.model_dump()
    event_values["db_level"] = calibrated_db(db, event_data.device, event_values["db_level"])
    if event_values["avg_db_level"] is not None:
        event_values["avg_db_level"] = calibrated_db(
            db, event_data.device, event_values["avg_db_level"]
        )

    if event_values["end_timestamp"] is None:
        event_values["end_timestamp"] = event_values["timestamp"]

    if event_values["avg_db_level"] is None:
        event_values["avg_db_level"] = event_values["db_level"]

    learned_class = _learned_class_for_detection(db, event_data.label)
    if learned_class is None or learned_class[1] is None:
        contextual_class = _contextual_class_for_detection(
            db, event_data.timestamp, event_data.label, category
        )
        if contextual_class is not None:
            learned_class = contextual_class
    primary_code = (
        learned_class[0]
        if learned_class is not None
        else base_class_for_detection(event_data.label, category)
    )
    subclass_code = learned_class[1] if learned_class is not None else None
    primary = (
        db.scalar(select(EventClass).where(EventClass.code == primary_code))
        if primary_code
        else None
    )
    suppressed = bool(primary and primary.hidden_by_default)
    ignored = db.scalar(
        select(IgnoredDetectionPattern).where(
            IgnoredDetectionPattern.label_normalized
            == _normalized_detection_label(event_data.label),
            IgnoredDetectionPattern.confirmations >= 3,
        )
    )
    event = Event(
        **event_values,
        label_de=label_de,
        category=category,
        primary_class_code=primary_code,
        subclass_code=subclass_code,
        classification_status=(
            "ignored" if ignored else ("suggested" if learned_class else "automatic")
        ),
        display_suppressed=suppressed or ignored is not None,
        person_monitoring_excluded=False,
    )

    if ignored is not None:
        event.id = 0
        event.audio_available = False
        return event

    merged = merge_candidate(db, event)
    if merged is not None:
        db.commit()
        db.refresh(merged)
        merged.audio_available = (
            db.scalars(select(AudioClip).where(AudioClip.event_id == merged.id)).first() is not None
        )
        if not merged.display_suppressed:
            await live_hub.broadcast(db.info.get("tenant_id", 1), EventRead.model_validate(merged).model_dump())
        return merged

    db.add(event)
    db.commit()
    db.refresh(event)
    linked_clip = associate_nearest_clip(db, event)
    if linked_clip is None:
        snapshot = live_audio_hub.wav_snapshot(event.device)
        if snapshot is not None:
            try:
                linked_clip = store_training_clip(
                    db,
                    snapshot,
                    device_id=event.device,
                    trigger_id=f"server-{event.id}",
                    trigger_uptime_ms=0,
                    received_at=event.timestamp,
                )
                if linked_clip.event_id is None:
                    linked_clip.event_id = event.id
                    db.commit()
                if linked_clip.event_id == event.id:
                    logger.info(
                        "Server-Audioclip %s wurde mit Ereignis %s (%s) verknüpft",
                        linked_clip.id,
                        event.id,
                        event.device,
                    )
                else:
                    logger.warning(
                        "Server-Audioclip %s war bereits mit Ereignis %s verknüpft; "
                        "Ereignis %s bleibt ohne Aufnahme",
                        linked_clip.id,
                        linked_clip.event_id,
                        event.id,
                    )
            except (OSError, ValueError):
                logger.exception(
                    "Server-Audioclip für Ereignis %s (%s) konnte nicht gespeichert werden",
                    event.id,
                    event.device,
                )
                linked_clip = None
        else:
            logger.warning(
                "Kein ausreichender Audio-Ringpuffer für Ereignis %s (%s) verfügbar",
                event.id,
                event.device,
            )
    event.audio_available = linked_clip is not None and linked_clip.event_id == event.id
    device = db.scalar(select(Device).where(Device.device_id == event.device))
    if device is None:
        db.add(Device(device_id=event.device, name=event.device, last_seen=event.timestamp))
    else:
        device.last_seen = event.timestamp
    db.commit()
    if not event.display_suppressed:
        await live_hub.broadcast(db.info.get("tenant_id", 1), EventRead.model_validate(event).model_dump())
        trigger_notifications(db, event)
        background_tasks.add_task(send_event_pushes, event.id)

    return event


@router.post("/clips/{device_id}", status_code=status.HTTP_201_CREATED)
def ingest_training_clip(
    device_id: str,
    payload: Annotated[bytes, Body(media_type="audio/wav")],
    db: DatabaseSession,
    _: Annotated[None, Depends(verify_ingest_key)],
    x_trigger_id: Annotated[str, Header(max_length=64)],
    x_trigger_uptime_ms: Annotated[int, Header(ge=0)],
    x_received_at: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _ensure_ingest_device(db, device_id)
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise HTTPException(status_code=404, detail="Unknown device")
    try:
        clip = store_training_clip(
            db,
            payload,
            device_id=device_id,
            trigger_id=x_trigger_id,
            trigger_uptime_ms=x_trigger_uptime_ms,
            received_at=x_received_at or datetime.now(UTC).isoformat(),
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    associate_nearest_event(db, clip)
    db.commit()
    return {"clip_id": clip.id, "sha256": clip.sha256, "event_id": clip.event_id}


@router.get("/training-examples", response_model=list[TrainingExampleRead])
def training_examples(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[TrainingExampleRead]:
    rows = db.execute(
        select(Event, AudioClip, EventClass)
        .join(AudioClip, AudioClip.event_id == Event.id)
        .join(EventClass, EventClass.code == Event.subclass_code)
        .where(
            Event.classification_status == "manual",
            Event.primary_class_code.is_not(None),
            Event.subclass_code.is_not(None),
        )
        .order_by(Event.id)
    ).all()
    return [
        TrainingExampleRead(
            event_id=event.id,
            device_id=clip.device_id,
            timestamp=event.timestamp,
            primary_class_code=event.primary_class_code,
            subclass_code=event.subclass_code,
            label=event_class.name,
            confidence=event.confidence,
            clip_sha256=clip.sha256,
            audio_url=f"/events/training-examples/{event.id}/audio",
        )
        for event, clip, event_class in rows
    ]


@router.get("/training-examples/{event_id}/audio")
def training_example_audio(
    event_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> FileResponse:
    clip = db.scalars(select(AudioClip).where(AudioClip.event_id == event_id)).first()
    event = db.get(Event, event_id)
    if (
        clip is None
        or event is None
        or event.classification_status != "manual"
        or event.subclass_code is None
    ):
        raise HTTPException(status_code=404, detail="Trainingsbeispiel nicht gefunden")
    return FileResponse(clip.path, media_type="audio/wav", filename=f"event-{event_id}.wav")


@router.get("/{event_id}/audio")
def event_audio(
    event_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> FileResponse:
    clip = db.scalar(select(AudioClip).where(AudioClip.event_id == event_id))
    if clip is None:
        raise HTTPException(
            status_code=404, detail="Für dieses Ereignis ist kein Audioclip vorhanden"
        )
    return FileResponse(clip.path, media_type="audio/wav", filename=f"event-{event_id}.wav")


def _validate_classes(
    db: Session, primary_code: str, subclass_code: str | None
) -> tuple[EventClass, EventClass | None]:
    primary = db.scalar(select(EventClass).where(EventClass.code == primary_code))
    if primary is None or primary.level != "base" or not primary.active:
        raise HTTPException(status_code=422, detail="Ungültige oder inaktive Basisklasse")
    subclass = None
    if subclass_code:
        subclass = db.scalar(select(EventClass).where(EventClass.code == subclass_code))
        if (
            subclass is None
            or subclass.level != "fine"
            or not subclass.active
            or subclass.parent_code not in (None, primary.code)
        ):
            raise HTTPException(status_code=422, detail="Feinzuordnung passt nicht zur Basisklasse")
    return primary, subclass


def _assign_manual(
    event: Event, primary: EventClass, subclass: EventClass | None, user: User, reason: str
) -> None:
    now = datetime.now(UTC).isoformat()
    event.primary_class_code = primary.code
    event.subclass_code = subclass.code if subclass else None
    event.classification_status = "manual"
    event.corrected_by = user.username
    event.corrected_at = now
    event.display_suppressed = primary.hidden_by_default


def _import_wav(db: Session, name: str, payload: bytes, device_id: str) -> bool:
    digest = hashlib.sha256(payload).hexdigest()
    if db.scalar(select(AudioClip).where(AudioClip.sha256 == digest)):
        return False
    try:
        with wave.open(io.BytesIO(payload), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frame_count = source.getnframes()
            frames = source.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"{name}: ungültige WAV-Datei") from exc
    if channels != 1 or sample_width != 2 or not frames:
        raise ValueError(f"{name}: benötigt Mono-PCM mit 16 Bit")
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    average_db = round(max(0.0, 94 + 20 * math.log10(max(rms, 1) / 32768)), 1)
    peak_db = round(max(average_db, 94 + 20 * math.log10(max(peak, 1) / 32768)), 1)
    timestamp = datetime.now(UTC).isoformat()
    duration = frame_count / sample_rate
    event = Event(
        timestamp=timestamp,
        end_timestamp=(datetime.now(UTC) + timedelta(seconds=duration)).isoformat(),
        duration_seconds=duration,
        event_type="HISTORICAL_AUDIO",
        label="Unknown historical audio",
        label_de="Historische Audioaufnahme",
        category="OTHER",
        confidence=0.0,
        db_level=peak_db,
        avg_db_level=average_db,
        device=device_id,
        classification_status="automatic",
    )
    db.add(event)
    db.flush()
    target = Path(settings.clip_directory) / f"import-{digest}.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    db.add(
        AudioClip(
            device_id=device_id,
            trigger_id=f"import-{event.id}",
            received_at=timestamp,
            sha256=digest,
            path=str(target),
            frame_count=frame_count,
            sample_rate=sample_rate,
            event_id=event.id,
        )
    )
    return True


def _import_csv(db: Session, name: str, payload: bytes, default_device: str) -> int:
    try:
        rows = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name}: CSV muss UTF-8-kodiert sein") from exc
    imported = 0
    for row in rows:
        timestamp = row.get("timestamp") or row.get("Zeitstempel")
        level = row.get("db_level") or row.get("dB") or row.get("pegel")
        if not timestamp or not level:
            continue
        label = row.get("label") or row.get("Ereignis") or "Historischer Messwert"
        label_de, category = translate_label(label, row.get("device") or default_device)
        db.add(
            Event(
                timestamp=timestamp,
                end_timestamp=timestamp,
                duration_seconds=float(row.get("duration_seconds") or 0),
                event_type="HISTORICAL_CSV",
                label=label,
                label_de=label_de,
                category=category,
                confidence=float(row.get("confidence") or 0),
                db_level=float(level.replace(",", ".")),
                avg_db_level=float(level.replace(",", ".")),
                device=row.get("device") or default_device,
                classification_status="automatic",
            )
        )
        imported += 1
    return imported


@router.post("/review/import", response_model=HistoricalImportResult)
def import_historical_data(
    data: HistoricalImportRequest,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> HistoricalImportResult:
    files: list[tuple[str, bytes]] = []
    total_size = 0
    for item in data.files:
        try:
            payload = base64.b64decode(item.content_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{item.name}: ungültige Daten") from exc
        total_size += len(payload)
        if total_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Import ist auf 50 MB begrenzt")
        if item.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    for member in archive.infolist():
                        suffix = Path(member.filename).suffix.lower()
                        if not member.is_dir() and suffix in {".wav", ".csv"}:
                            total_size += member.file_size
                            if total_size > 50 * 1024 * 1024:
                                raise HTTPException(
                                    status_code=413,
                                    detail="Entpackter Import ist auf 50 MB begrenzt",
                                )
                            files.append((Path(member.filename).name, archive.read(member)))
            except zipfile.BadZipFile as exc:
                raise HTTPException(status_code=422, detail=f"{item.name}: ungültiges ZIP") from exc
        else:
            files.append((Path(item.name).name, payload))
    if len(files) > 100:
        raise HTTPException(
            status_code=413, detail="Import ist auf 100 enthaltene Dateien begrenzt"
        )
    imported_audio = imported_events = skipped = 0
    messages: list[str] = []
    for name, payload in files:
        try:
            if name.lower().endswith(".wav"):
                created = _import_wav(db, name, payload, data.device_id)
                imported_audio += int(created)
                imported_events += int(created)
                skipped += int(not created)
            elif name.lower().endswith(".csv"):
                count = _import_csv(db, name, payload, data.device_id)
                imported_events += count
                messages.append(f"{name}: {count} Messwerte")
            else:
                skipped += 1
        except (ValueError, wave.Error) as exc:
            skipped += 1
            messages.append(str(exc))
    db.commit()
    return HistoricalImportResult(
        imported_events=imported_events,
        imported_audio=imported_audio,
        skipped=skipped,
        messages=messages,
    )


@router.get("/review/summary", response_model=ReviewSummary)
def review_summary(
    db: DatabaseSession,
    _: CurrentUser,
    start: str | None = None,
    end: str | None = None,
) -> ReviewSummary:
    statement = select(Event)
    if start:
        statement = statement.where(Event.timestamp >= start)
    if end:
        statement = statement.where(Event.timestamp < end)
    events = list(db.scalars(statement))
    summary = {
        "open_unknown": 0,
        "open_recognized": 0,
        "completed_unknown": 0,
        "completed_recognized": 0,
        "excluded_context_only": 0,
    }
    by_class: dict[str, dict[str, int]] = {}
    for event in events:
        if event.classification_status == "context_only":
            summary["excluded_context_only"] += 1
            continue
        completed = event.classification_status in {"manual", "learned"}
        recognized = event.primary_class_code is not None
        summary[
            f"{'completed' if completed else 'open'}_{'recognized' if recognized else 'unknown'}"
        ] += 1
        code = event.subclass_code or event.primary_class_code or "UNKNOWN"
        counts = by_class.setdefault(code, {"open": 0, "completed": 0})
        counts["completed" if completed else "open"] += 1
    return ReviewSummary(**summary, by_class=by_class)


@router.get("/review/queue", response_model=list[ReviewQueueItem])
def review_queue(
    db: DatabaseSession,
    _: CurrentUser,
    class_code: str | None = None,
    status_filter: str = Query(default="open", alias="status", pattern="^(open|completed|all)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    start: str | None = None,
    end: str | None = None,
) -> list[Event]:
    statement = (
        select(Event)
        .join(AudioClip, AudioClip.event_id == Event.id)
        .where(Event.classification_status != "context_only")
        .distinct()
    )
    if status_filter == "open":
        statement = statement.where(Event.classification_status.not_in(("manual", "learned")))
    elif status_filter == "completed":
        statement = statement.where(Event.classification_status.in_(("manual", "learned")))
    if class_code == "UNKNOWN":
        statement = statement.where(Event.primary_class_code.is_(None))
    elif class_code:
        statement = statement.where(
            (Event.primary_class_code == class_code) | (Event.subclass_code == class_code)
        )
    if start:
        statement = statement.where(Event.timestamp >= start)
    if end:
        statement = statement.where(Event.timestamp < end)
    events = list(db.scalars(statement.order_by(desc(Event.id)).limit(limit)))
    event_ids = {event.id for event in events}
    audio_event_ids = (
        set(db.scalars(select(AudioClip.event_id).where(AudioClip.event_id.in_(event_ids))).all())
        if event_ids
        else set()
    )
    for event in events:
        event.audio_available = event.id in audio_event_ids
    assignments = {
        item.event_id: item.person_id
        for item in db.scalars(
            select(EventPersonAssignment).where(EventPersonAssignment.event_id.in_(event_ids))
        )
    }
    for event in events:
        event.person_id = assignments.get(event.id)
    return events


@router.post("/review/bulk-classification", response_model=list[EventRead])
def bulk_classification(
    data: BulkClassificationUpdate,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[Event]:
    primary, subclass = _validate_classes(db, data.primary_class_code, data.subclass_code)
    events = list(db.scalars(select(Event).where(Event.id.in_(set(data.event_ids)))))
    if len(events) != len(set(data.event_ids)):
        raise HTTPException(status_code=404, detail="Mindestens ein Ereignis wurde nicht gefunden")
    for event in events:
        _assign_manual(event, primary, subclass, user, data.reason)
        db.add(
            EventClassificationRevision(
                event_id=event.id,
                primary_class_code=primary.code,
                subclass_code=event.subclass_code,
                status="manual",
                actor=user.username,
                reason=data.reason,
                created_at=event.corrected_at,
            )
        )
    db.flush()
    for event in events:
        _apply_learned_classifications(db, event)
    db.commit()
    return events


@router.get("/review/runs", response_model=list[ReviewRunRead])
def review_runs(db: DatabaseSession, _: CurrentUser) -> list[ReviewRun]:
    return list(db.scalars(select(ReviewRun).order_by(desc(ReviewRun.id)).limit(20)))


@router.post("/review/runs", response_model=ReviewRunRead, status_code=201)
def start_review_run(
    data: ReviewRunCreate,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    active = db.scalar(select(ReviewRun).where(ReviewRun.status.in_(("pending", "running"))))
    if active:
        raise HTTPException(status_code=409, detail="Es läuft bereits ein Prüflauf")
    run = ReviewRun(kind=data.kind, status="pending", requested_by=user.username)
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(process_review_run, run.id)
    return run


@router.post("/review/runs/{run_id}/pause", response_model=ReviewRunRead)
def pause_review_run(
    run_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    run = db.get(ReviewRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Prüflauf nicht gefunden")
    if run.status in {"pending", "running"}:
        run.status = "paused"
        run.message = "Prüflauf manuell unterbrochen."
        db.commit()
    return run


@router.post("/review/runs/{run_id}/resume", response_model=ReviewRunRead)
def resume_review_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> ReviewRun:
    run = db.get(ReviewRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Prüflauf nicht gefunden")
    if run.status != "paused":
        raise HTTPException(
            status_code=409, detail="Nur unterbrochene Prüfläufe können fortgesetzt werden"
        )
    run.status = "pending"
    run.message = ""
    db.commit()
    background_tasks.add_task(process_review_run, run.id)
    return run


@router.get("/{event_id}/assessment")
def event_assessment(event_id: int, db: DatabaseSession, _: CurrentUser) -> dict[str, object]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    config = db.scalar(select(AssessmentConfig).order_by(AssessmentConfig.id)) or AssessmentConfig()
    return assessment_for(
        event.timestamp,
        event.db_level,
        config.sensitive_surcharge_db,
        config.apply_to_live,
    )


@router.put("/{event_id}/person", status_code=204)
def assign_event_person(
    event_id: int,
    data: PersonAssignmentWrite,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> None:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    assignment = db.scalar(
        select(EventPersonAssignment).where(EventPersonAssignment.event_id == event_id)
    )
    if data.person_id is None:
        if assignment:
            db.delete(assignment)
        event.person_monitoring_excluded = False
        db.commit()
        return
    person = db.get(PersonProfile, data.person_id)
    if person is None or not person.active:
        raise HTTPException(status_code=422, detail="Person nicht gefunden oder inaktiv")
    if assignment is None:
        assignment = EventPersonAssignment(event_id=event_id, person_id=person.id)
        db.add(assignment)
    else:
        assignment.person_id = person.id
        assignment.source = "manual"
        assignment.confidence = 1.0
        assignment.confirmed = True
        assignment.assigned_at = datetime.now(UTC).isoformat()
    event.person_monitoring_excluded = not person.monitoring_enabled
    db.commit()


@router.post("/{event_id}/ignore", status_code=204)
def ignore_event_as_no_noise(
    event_id: int,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> None:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    normalized = _normalized_detection_label(event.label)
    pattern = db.scalar(
        select(IgnoredDetectionPattern).where(
            IgnoredDetectionPattern.label_normalized == normalized
        )
    )
    now = datetime.now(UTC).isoformat()
    if pattern is None:
        pattern = IgnoredDetectionPattern(
            label_normalized=normalized,
            label_example=event.label[:160],
            confirmations=1,
            created_at=now,
            updated_at=now,
        )
        db.add(pattern)
    else:
        pattern.confirmations += 1
        pattern.updated_at = now
    clip = db.scalar(select(AudioClip).where(AudioClip.event_id == event_id))
    clip_path = Path(clip.path) if clip is not None else None
    if clip is not None:
        db.delete(clip)
    db.delete(event)
    db.commit()
    if clip_path is not None:
        try:
            clip_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Audioclip für verworfenes Ereignis %s konnte nicht gelöscht werden",
                event_id,
            )
    logger.info(
        "Ereignis %s wurde von %s als kein Lärm verworfen; Lernmuster %s hat %s Bestätigungen",
        event_id,
        user.username,
        normalized,
        pattern.confirmations,
    )


@router.patch("/{event_id}/classification", response_model=EventRead)
async def correct_event_classification(
    event_id: int,
    data: EventClassificationUpdate,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    primary, subclass = _validate_classes(db, data.primary_class_code, data.subclass_code)
    _assign_manual(event, primary, subclass, user, data.reason)
    db.add(
        EventClassificationRevision(
            event_id=event.id,
            primary_class_code=primary.code,
            subclass_code=event.subclass_code,
            status="manual",
            actor=user.username,
            reason=data.reason,
            created_at=event.corrected_at,
        )
    )
    db.flush()
    _apply_learned_classifications(db, event)
    db.commit()
    db.refresh(event)
    await live_hub.broadcast(db.info.get("tenant_id", 1), EventRead.model_validate(event).model_dump())
    return event


@router.get(
    "/{event_id}/classification-history",
    response_model=list[EventClassificationRevisionRead],
)
def event_classification_history(
    event_id: int,
    db: DatabaseSession,
    _: CurrentUser,
) -> list[EventClassificationRevision]:
    if db.get(Event, event_id) is None:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden")
    return list(
        db.scalars(
            select(EventClassificationRevision)
            .where(EventClassificationRevision.event_id == event_id)
            .order_by(EventClassificationRevision.id)
        )
    )


@router.get(
    "",
    response_model=list[EventRead],
)
def list_events(
    db: DatabaseSession,
    _: CurrentUser,
    limit: int = Query(default=100, ge=1, le=1000),
    device: str | None = None,
    category: str | None = None,
    start: str | None = None,
    end: str | None = None,
    include_suppressed: bool = False,
) -> list[Event]:
    statement = select(Event)
    if not include_suppressed:
        statement = statement.where(Event.display_suppressed.is_(False))
    if device:
        statement = statement.where(Event.device == device)
    if category:
        statement = statement.where(Event.category == category)
    if start:
        statement = statement.where(Event.timestamp >= start)
    if end:
        statement = statement.where(Event.timestamp <= end)
    statement = statement.order_by(desc(Event.id)).limit(limit)

    events = list(db.scalars(statement).all())
    event_ids = {event.id for event in events}
    audio_event_ids = (
        set(db.scalars(select(AudioClip.event_id).where(AudioClip.event_id.in_(event_ids))).all())
        if event_ids
        else set()
    )
    for event in events:
        event.audio_available = event.id in audio_event_ids
    assignments = {
        item.event_id: item.person_id
        for item in db.scalars(
            select(EventPersonAssignment).where(EventPersonAssignment.event_id.in_(event_ids))
        )
    } if event_ids else {}
    for event in events:
        event.person_id = assignments.get(event.id)
    return events
