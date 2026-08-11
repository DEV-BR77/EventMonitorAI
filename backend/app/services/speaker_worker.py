import json
import os
import time
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sqlalchemy import delete, or_, select

from app.database.session import SessionLocal
from app.models.dashboard import (
    AudioClip,
    EventSpeakerCluster,
    SpeakerAnalysisRun,
    SpeakerCluster,
)
from app.models.event import Event

ECAPA_ALGORITHM = "speechbrain-ecapa-voxceleb"
MODEL_NAME = "speechbrain/spkrec-ecapa-voxceleb"
VOICE_CATEGORIES = {"VOICE", "VOCALIZATION", "HUMAN_SOUND"}


def _load_encoder():
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    torch.set_num_threads(max(1, int(os.getenv("SPEAKER_WORKER_THREADS", "2"))))
    return EncoderClassifier.from_hparams(
        source=MODEL_NAME,
        savedir=os.getenv("SPEAKER_MODEL_CACHE", "/models/ecapa-voxceleb"),
        run_opts={"device": "cpu"},
    )


def _embedding(encoder, path: str) -> np.ndarray:
    import torch

    with wave.open(str(Path(path)), "rb") as audio:
        channels = audio.getnchannels()
        sample_rate = audio.getframerate()
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(
            np.float32
        )
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if sample_rate != 16_000 or len(samples) < 8_000:
        raise ValueError("Stimmclip benötigt mindestens 0,5 s Mono-Audio mit 16 kHz")
    waveform = torch.from_numpy(samples / 32768.0).unsqueeze(0)
    with torch.inference_mode():
        vector = encoder.encode_batch(waveform).squeeze().cpu().numpy().astype(np.float32)
    vector /= max(float(np.linalg.norm(vector)), 1e-9)
    return vector


def _voice_rows(db):
    return db.execute(
        select(Event, AudioClip)
        .join(AudioClip, AudioClip.event_id == Event.id)
        .where(
            or_(
                Event.category.in_(VOICE_CATEGORIES),
                Event.primary_class_code == "VOICE_LOUD",
                Event.label.ilike("%speech%"),
                Event.label.ilike("%shout%"),
                Event.label.ilike("%scream%"),
                Event.label.ilike("%voice%"),
            )
        )
        .order_by(Event.timestamp)
    ).all()


def process_run(run_id: int, encoder=None):
    with SessionLocal() as root:
        root.info["include_all_tenants"] = True
        run = root.get(SpeakerAnalysisRun, run_id)
        if run is None or run.status != "pending":
            return
        tenant_id = run.tenant_id
        run.status = "running"
        run.started_at = datetime.now(UTC).isoformat()
        run.message = "ECAPA-TDNN-Modell wird geladen."
        root.commit()

    try:
        encoder = encoder or _load_encoder()
        threshold = float(os.getenv("SPEAKER_SIMILARITY_THRESHOLD", "0.72"))
        with SessionLocal() as db:
            db.info["tenant_id"] = tenant_id
            run = db.get(SpeakerAnalysisRun, run_id)
            rows = _voice_rows(db)
            run.total = len(rows)
            run.message = "Sprachaufnahmen werden lokal analysiert."
            # A complete manual rerun replaces technical group assignments. Explicit
            # EventPersonAssignment rows are a separate table and remain untouched.
            db.execute(delete(EventSpeakerCluster))
            for cluster in db.scalars(select(SpeakerCluster)):
                db.delete(cluster)
            db.commit()
            clusters: list[tuple[SpeakerCluster, np.ndarray]] = []
            for event, clip in rows:
                try:
                    vector = _embedding(encoder, clip.path)
                except (OSError, ValueError, wave.Error):
                    run.skipped += 1
                    run.processed += 1
                    db.commit()
                    continue
                scores = [float(np.dot(vector, centroid)) for _, centroid in clusters]
                score = max(scores, default=-1.0)
                if score < threshold:
                    cluster = SpeakerCluster(
                        name=f"Stimme {len(clusters) + 1}",
                        centroid_json=json.dumps(vector.tolist()),
                        sample_count=0,
                        algorithm=ECAPA_ALGORITHM,
                    )
                    db.add(cluster)
                    db.flush()
                    clusters.append((cluster, vector))
                    index = len(clusters) - 1
                    score = 1.0
                else:
                    index = int(np.argmax(scores))
                cluster, centroid = clusters[index]
                count = cluster.sample_count
                updated = centroid * count + vector
                updated /= max(float(np.linalg.norm(updated)), 1e-9)
                cluster.sample_count = count + 1
                cluster.centroid_json = json.dumps(updated.tolist())
                cluster.updated_at = datetime.now(UTC).isoformat()
                clusters[index] = (cluster, updated)
                db.add(
                    EventSpeakerCluster(
                        event_id=event.id,
                        cluster_id=cluster.id,
                        similarity=score,
                        review_status="pending",
                    )
                )
                run.processed += 1
                run.clustered = len(clusters)
                if run.processed % 10 == 0:
                    run.message = f"{run.processed} von {run.total} Aufnahmen analysiert."
                    db.commit()
            run.status = "completed"
            run.finished_at = datetime.now(UTC).isoformat()
            run.message = "Lokale ECAPA-Stimmanalyse abgeschlossen."
            db.commit()
        return encoder
    except Exception as exc:
        with SessionLocal() as db:
            db.info["include_all_tenants"] = True
            run = db.get(SpeakerAnalysisRun, run_id)
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(UTC).isoformat()
                run.message = str(exc)[:500]
                db.commit()


def run_worker() -> None:
    encoder = None
    while True:
        with SessionLocal() as db:
            db.info["include_all_tenants"] = True
            run_id = db.scalar(
                select(SpeakerAnalysisRun.id)
                .where(SpeakerAnalysisRun.status == "pending")
                .order_by(SpeakerAnalysisRun.id)
                .limit(1)
            )
        if run_id is None:
            time.sleep(2)
            continue
        encoder = process_run(run_id, encoder) or encoder
