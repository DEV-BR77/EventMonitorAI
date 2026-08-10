import base64
import binascii
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dashboard import PersonProfile, SpeakerCluster
from app.services.speaker_clustering import voiceprint

MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_PHOTO_BYTES = 5 * 1024 * 1024
VIDEO_MIMES = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}
PHOTO_MIMES = {"image/jpeg": ".jpg", "image/png": ".png"}


def _decode(content_base64: str, maximum: int) -> bytes:
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Datei ist nicht gültig Base64-kodiert") from error
    if not data or len(data) > maximum:
        raise ValueError(f"Dateigröße muss zwischen 1 Byte und {maximum // 1024 // 1024} MB liegen")
    return data


def _validate_signature(data: bytes, mime_type: str) -> None:
    if mime_type == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("JPEG-Datei hat keine gültige Signatur")
    if mime_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG-Datei hat keine gültige Signatur")
    if mime_type in {"video/mp4", "video/quicktime"} and data[4:8] != b"ftyp":
        raise ValueError("MP4/MOV-Datei hat keine gültige Signatur")
    if mime_type == "video/webm" and not data.startswith(b"\x1aE\xdf\xa3"):
        raise ValueError("WebM-Datei hat keine gültige Signatur")


def _store(data: bytes, person_id: int, suffix: str, kind: str) -> Path:
    root = Path(settings.person_media_directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:16]
    target = (root / f"person-{person_id}-{kind}-{digest}{suffix}").resolve()
    if root not in target.parents:
        raise ValueError("Ungültiger Medienpfad")
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return target


def store_photo(person: PersonProfile, content_base64: str, mime_type: str) -> Path:
    suffix = PHOTO_MIMES.get(mime_type)
    if suffix is None:
        raise ValueError("Als Profilbild sind nur JPEG und PNG erlaubt")
    data = _decode(content_base64, MAX_PHOTO_BYTES)
    _validate_signature(data, mime_type)
    target = _store(data, person.id, suffix, "photo")
    person.photo_path = str(target)
    return target


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.clip(np.dot(left, right), -1, 1))


def store_video_and_compare(
    db: Session, person: PersonProfile, content_base64: str, mime_type: str
) -> dict[str, object]:
    suffix = VIDEO_MIMES.get(mime_type)
    if suffix is None:
        raise ValueError("Als Prüfvideo sind nur MP4, MOV und WebM erlaubt")
    data = _decode(content_base64, MAX_VIDEO_BYTES)
    _validate_signature(data, mime_type)
    video_path = _store(data, person.id, suffix, "video")
    audio_path = video_path.with_suffix(".voice.wav")
    try:
        process = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-y", "-i", str(video_path), "-vn", "-ac", "1",
                "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path),
            ],
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Die Videoverarbeitung hat länger als 45 Sekunden gedauert") from error
    person.video_path = str(video_path)
    person.video_audio_path = None
    person.video_voice_similarity = None
    person.video_voice_cluster_id = None
    if process.returncode != 0 or not audio_path.exists():
        return {"audio_extracted": False, "message": "Video gespeichert, aber keine verwertbare Tonspur gefunden"}

    try:
        vector = voiceprint(str(audio_path))
    except (OSError, ValueError) as error:
        return {"audio_extracted": False, "message": f"Tonspur gespeichert, aber nicht als Stimme verwertbar: {error}"}
    person.video_audio_path = str(audio_path)
    scored = []
    for cluster in db.scalars(select(SpeakerCluster)):
        centroid = np.asarray(json.loads(cluster.centroid_json), dtype=np.float32)
        scored.append((_cosine(vector, centroid), cluster))
    linked = [item for item in scored if item[1].linked_person_id == person.id]
    candidates = linked or scored
    if candidates:
        similarity, cluster = max(candidates, key=lambda item: item[0])
        person.video_voice_similarity = round(similarity, 4)
        person.video_voice_cluster_id = cluster.id
        scope = "bestätigten Stimmprofil" if linked else "besten anonymen Stimmgruppe"
        return {
            "audio_extracted": True,
            "similarity": person.video_voice_similarity,
            "cluster_id": cluster.id,
            "cluster_name": cluster.name,
            "message": f"Tonspur mit dem {scope} verglichen",
        }
    return {"audio_extracted": True, "message": "Tonspur extrahiert; noch keine Stimmgruppe zum Vergleich vorhanden"}
