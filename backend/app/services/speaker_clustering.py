import json
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.dashboard import (
    AudioClip,
    EventPersonAssignment,
    EventSpeakerCluster,
    PersonProfile,
    SpeakerCluster,
)
from app.models.event import Event

ALGORITHM = "voiceprint-v1"
SIMILARITY_THRESHOLD = 0.90
VOICE_CATEGORIES = {"VOICE", "VOCALIZATION", "HUMAN_SOUND"}


def voiceprint(path: str) -> np.ndarray:
    with wave.open(str(Path(path)), "rb") as audio:
        channels = audio.getnchannels()
        sample_rate = audio.getframerate()
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(
            np.float32
        )
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if not len(samples):
        raise ValueError("Leere Audioaufnahme")
    samples /= 32768.0
    if sample_rate != 16_000:
        target_length = max(1, round(len(samples) * 16_000 / sample_rate))
        samples = np.interp(
            np.linspace(0, len(samples) - 1, target_length), np.arange(len(samples)), samples
        ).astype(np.float32)
    frame_size, hop = 400, 160
    if len(samples) < frame_size:
        samples = np.pad(samples, (0, frame_size - len(samples)))
    frames = np.lib.stride_tricks.sliding_window_view(samples, frame_size)[::hop]
    energy = np.sqrt(np.mean(frames * frames, axis=1) + 1e-9)
    active = frames[energy >= np.percentile(energy, 45)]
    if not len(active):
        active = frames
    spectrum = np.abs(np.fft.rfft(active * np.hanning(frame_size), n=512)) + 1e-8
    frequencies = np.fft.rfftfreq(512, 1 / 16_000)
    edges = np.geomspace(100, 4_500, 25)
    bands = []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        start = int(np.searchsorted(frequencies, low, side="left"))
        stop = max(start + 1, int(np.searchsorted(frequencies, high, side="right")))
        bands.append(np.log(spectrum[:, start:stop].mean(axis=1) + 1e-8))
    features = np.stack(bands, axis=1)
    vector = np.concatenate((features.mean(axis=0), features.std(axis=0)))
    vector -= vector.mean()
    norm = np.linalg.norm(vector)
    if norm <= 1e-9:
        raise ValueError("Kein verwertbares Stimmsignal")
    return (vector / norm).astype(np.float32)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.clip(np.dot(left, right), -1, 1))


def cluster_existing_voice_clips(db: Session) -> dict[str, int]:
    assigned_events = set(db.scalars(select(EventSpeakerCluster.event_id)))
    rows = db.execute(
        select(Event, AudioClip)
        .join(AudioClip, AudioClip.event_id == Event.id)
        .where(
            Event.id.not_in(assigned_events) if assigned_events else True,
            or_(
                Event.category.in_(VOICE_CATEGORIES),
                Event.primary_class_code == "VOICE_LOUD",
                Event.label.ilike("%speech%"),
                Event.label.ilike("%shout%"),
                Event.label.ilike("%scream%"),
                Event.label.ilike("%voice%"),
            ),
        )
        .order_by(Event.timestamp)
    ).all()
    clusters: list[tuple[SpeakerCluster, np.ndarray]] = []
    for existing in db.scalars(select(SpeakerCluster).order_by(SpeakerCluster.id)):
        clusters.append(
            (existing, np.asarray(json.loads(existing.centroid_json), dtype=np.float32))
        )
    used_names = {item.name for item, _ in clusters}
    analyzed = skipped = 0
    for event, clip in rows:
        try:
            vector = voiceprint(clip.path)
        except (OSError, ValueError, wave.Error):
            skipped += 1
            continue
        analyzed += 1
        scores = [
            (_cosine(vector, centroid), index) for index, (_, centroid) in enumerate(clusters)
        ]
        score, index = max(scores, default=(-1.0, -1))
        if score < SIMILARITY_THRESHOLD:
            number = 1
            while f"Person {number}" in used_names:
                number += 1
            cluster = SpeakerCluster(
                name=f"Person {number}",
                centroid_json=json.dumps(vector.tolist()),
                sample_count=0,
                algorithm=ALGORITHM,
            )
            db.add(cluster)
            db.flush()
            clusters.append((cluster, vector))
            used_names.add(cluster.name)
            index = len(clusters) - 1
            score = 1.0
        cluster, centroid = clusters[index]
        has_confirmed = db.scalar(
            select(EventSpeakerCluster.id).where(
                EventSpeakerCluster.cluster_id == cluster.id,
                EventSpeakerCluster.review_status == "confirmed",
            ).limit(1)
        )
        if has_confirmed is None:
            count = cluster.sample_count
            updated = centroid * count + vector
            updated /= max(np.linalg.norm(updated), 1e-9)
            cluster.sample_count = count + 1
            cluster.centroid_json = json.dumps(updated.tolist())
            clusters[index] = (cluster, updated)
        cluster.updated_at = datetime.now(UTC).isoformat()
        db.add(EventSpeakerCluster(event_id=event.id, cluster_id=cluster.id, similarity=score))
    db.commit()
    return {"analyzed": analyzed, "clusters": len(clusters), "skipped": skipped}


def recompute_cluster_centroid(db: Session, cluster: SpeakerCluster) -> None:
    assignments = list(
        db.scalars(
            select(EventSpeakerCluster).where(
                EventSpeakerCluster.cluster_id == cluster.id,
                EventSpeakerCluster.review_status == "confirmed",
            )
        )
    )
    if not assignments:
        assignments = list(
            db.scalars(
                select(EventSpeakerCluster).where(
                    EventSpeakerCluster.cluster_id == cluster.id,
                    EventSpeakerCluster.review_status == "pending",
                )
            )
        )
    vectors: list[np.ndarray] = []
    for assignment in assignments:
        clip = db.scalar(select(AudioClip).where(AudioClip.event_id == assignment.event_id))
        if clip is None:
            continue
        try:
            vectors.append(voiceprint(clip.path))
        except (OSError, ValueError, wave.Error):
            continue
    if vectors:
        centroid = np.mean(vectors, axis=0)
        centroid /= max(np.linalg.norm(centroid), 1e-9)
        cluster.centroid_json = json.dumps(centroid.tolist())
    cluster.sample_count = len(assignments)
    cluster.updated_at = datetime.now(UTC).isoformat()


def create_cluster_from_event(db: Session, event_id: int) -> SpeakerCluster:
    clip = db.scalar(select(AudioClip).where(AudioClip.event_id == event_id))
    if clip is None:
        raise ValueError("Für dieses Ereignis ist kein Audioclip vorhanden")
    vector = voiceprint(clip.path)
    used_names = set(db.scalars(select(SpeakerCluster.name)))
    number = 1
    while f"Person {number}" in used_names:
        number += 1
    cluster = SpeakerCluster(
        name=f"Person {number}",
        centroid_json=json.dumps(vector.tolist()),
        sample_count=1,
        algorithm=ALGORITHM,
    )
    db.add(cluster)
    db.flush()
    return cluster


def link_cluster_to_person(
    db: Session, cluster: SpeakerCluster, person: PersonProfile | None
) -> None:
    cluster.linked_person_id = person.id if person else None
    cluster.updated_at = datetime.now(UTC).isoformat()
    all_event_ids = set(
        db.scalars(
            select(EventSpeakerCluster.event_id).where(
                EventSpeakerCluster.cluster_id == cluster.id
            )
        )
    )
    for assignment in db.scalars(
        select(EventPersonAssignment).where(
            EventPersonAssignment.event_id.in_(all_event_ids),
            EventPersonAssignment.source == "speaker_cluster",
        )
    ):
        db.delete(assignment)
        event = db.get(Event, assignment.event_id)
        if event is not None:
            event.person_monitoring_excluded = False
    event_ids = set(
        db.scalars(
            select(EventSpeakerCluster.event_id).where(
                EventSpeakerCluster.cluster_id == cluster.id,
                EventSpeakerCluster.review_status == "confirmed",
            )
        )
    )
    if person is not None:
        for event_id in event_ids:
            assignment = db.scalar(
                select(EventPersonAssignment).where(EventPersonAssignment.event_id == event_id)
            )
            if assignment is None:
                db.add(
                    EventPersonAssignment(
                        event_id=event_id,
                        person_id=person.id,
                        source="speaker_cluster",
                        confidence=1.0,
                        confirmed=True,
                    )
                )
            else:
                assignment.person_id = person.id
                assignment.source = "speaker_cluster"
                assignment.confirmed = True
            event = db.get(Event, event_id)
            if event is not None:
                event.person_monitoring_excluded = not person.monitoring_enabled
    db.commit()
