"""Exportiere einen prüfbaren Golden-Dataset-Kandidaten aus Produktionsdaten.

Der Export liest nur; er verändert weder PostgreSQL noch das Clip-Volume.
Standardmäßig werden bereits fürs Lernen freigegebene Ereignisse ausgelassen,
weil sie für ein unabhängiges Golden Dataset kontaminiert sein können.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.database.session import SessionLocal
from app.models.dashboard import AudioClip, EventClass
from app.models.event import Event, EventSecondaryClassification
from sqlalchemy import select

FIELDS = (
    "sample_id", "event_id", "clip_id", "clip_sha256", "audio_file",
    "tenant_id", "device_id", "timestamp", "end_timestamp", "duration_seconds",
    "db_level", "avg_db_level", "primary_class_code", "subclass_code",
    "class_name", "classification_status", "reviewer", "reviewed_at",
    "primary_learning_approved", "secondary_class_codes", "source_trigger_id",
    "received_at", "sample_rate", "frame_count", "training_overlap_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--include-training-approved", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    audio_dir = args.output / "audio"
    audio_dir.mkdir(exist_ok=True)
    manifest_path = args.output / "manifest.csv"
    report_path = args.output / "EXPORT_REPORT.md"

    with SessionLocal() as db:
        statement = (
            select(Event, AudioClip, EventClass)
            .join(AudioClip, AudioClip.event_id == Event.id)
            .join(EventClass, EventClass.code == Event.subclass_code)
            .where(
                Event.classification_status == "manual",
                Event.primary_class_code.is_not(None),
                Event.subclass_code.is_not(None),
                Event.display_suppressed.is_(False),
            )
            .order_by(Event.id)
            .execution_options(include_all_tenants=True)
        )
        if args.tenant_id is not None:
            statement = statement.where(Event.tenant_id == args.tenant_id)

        rows = db.execute(statement).all()
        selected: list[dict[str, object]] = []
        excluded: Counter[str] = Counter()
        for event, clip, event_class in rows:
            if event.primary_learning_approved and not args.include_training_approved:
                excluded["primary_learning_approved"] += 1
                continue
            source = Path(clip.path)
            if not source.is_file():
                excluded["audio_file_missing"] += 1
                continue
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != clip.sha256:
                excluded["audio_hash_mismatch"] += 1
                continue
            sample_id = f"event-{event.id}-clip-{clip.id}"
            target = audio_dir / f"{sample_id}.wav"
            shutil.copy2(source, target)
            secondary = db.scalars(
                select(EventSecondaryClassification).where(
                    EventSecondaryClassification.event_id == event.id
                )
            ).all()
            selected.append({
                "sample_id": sample_id, "event_id": event.id, "clip_id": clip.id,
                "clip_sha256": clip.sha256, "audio_file": str(Path("audio") / target.name),
                "tenant_id": event.tenant_id, "device_id": clip.device_id,
                "timestamp": event.timestamp, "end_timestamp": event.end_timestamp,
                "duration_seconds": event.duration_seconds, "db_level": event.db_level,
                "avg_db_level": event.avg_db_level, "primary_class_code": event.primary_class_code,
                "subclass_code": event.subclass_code, "class_name": event_class.name,
                "classification_status": event.classification_status,
                "reviewer": event.corrected_by, "reviewed_at": event.corrected_at,
                "primary_learning_approved": event.primary_learning_approved,
                "secondary_class_codes": json.dumps([item.class_code for item in secondary]),
                "source_trigger_id": clip.trigger_id, "received_at": clip.received_at,
                "sample_rate": clip.sample_rate, "frame_count": clip.frame_count,
                "training_overlap_status": "unknown_requires_manifest_check",
            })

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(selected)
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    classes = Counter(str(row["subclass_code"]) for row in selected)
    report = [
        "# Golden-Candidate-Export", "", f"Erstellt: {datetime.now(UTC).isoformat()}",
        "", "Status: `candidate_requires_human_review`", "",
        "Der Export ist ein unveränderlicher Arbeitsbestand und noch kein Golden-v1-Freeze.",
        "Training-Overlap bleibt bis zur Prüfung der Modellmanifeste unbekannt.", "",
        f"- Samples exportiert: {len(selected)}",
        f"- Manifest-SHA-256: `{manifest_hash}`",
        f"- Klassen: {dict(sorted(classes.items())) or 'keine'}",
        f"- Ausgeschlossen: {dict(excluded) or 'keine'}", "",
        "Nächste Schritte: menschliche Reviewstatus/Begründungen prüfen, Support-"
        "Gate und Training-Overlap belegen, Near-Duplicates bewerten und erst danach"
        " Golden v1 einfrieren.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Exportiert: {len(selected)} Samples")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
