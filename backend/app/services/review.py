import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.dashboard import AudioClip, EventClassificationRevision, ReviewRun, Tenant
from app.models.event import Event
from app.services.taxonomy import base_class_for_detection


def mark_clipless_events_context_only(db: Session, *, actor: str = "system") -> int:
    """Exclude clipless metadata detections from acoustic review and learning."""
    events = list(
        db.scalars(
            select(Event)
            .outerjoin(AudioClip, AudioClip.event_id == Event.id)
            .where(
                AudioClip.id.is_(None),
                Event.classification_status.notin_(("ignored", "context_only")),
            )
            .order_by(Event.id)
        )
    )
    changed_at = datetime.now(UTC).isoformat()
    for event in events:
        previous_status = event.classification_status
        event.classification_status = "context_only"
        event.corrected_by = event.corrected_by or actor
        event.corrected_at = changed_at
        if event.primary_class_code:
            db.add(
                EventClassificationRevision(
                    event_id=event.id,
                    primary_class_code=event.primary_class_code,
                    subclass_code=event.subclass_code,
                    status="context_only",
                    actor=actor,
                    reason=(
                        "Kein gespeicherter Audioclip: bestehende Zuordnung bleibt als "
                        f"Metadaten-/Kontextwertung erhalten (vorher: {previous_status})."
                    ),
                )
            )
    db.commit()
    return len(events)


def process_review_run(run_id: int, batch_size: int = 100) -> None:
    with SessionLocal() as db:
        db.info["include_all_tenants"] = True
        run = db.get(ReviewRun, run_id)
        if run is None or run.status not in {"pending", "paused"}:
            return
        tenant_id = run.tenant_id
        db.info.pop("include_all_tenants", None)
        db.info["tenant_id"] = tenant_id
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC).isoformat()
        run.total = db.scalar(select(func.count()).select_from(Event)) or 0
        db.commit()

    while True:
        with SessionLocal() as db:
            db.info["include_all_tenants"] = True
            run = db.get(ReviewRun, run_id)
            if run is None or run.status != "running":
                return
            tenant_id = run.tenant_id
            db.info.pop("include_all_tenants", None)
            db.info["tenant_id"] = tenant_id
            events = list(
                db.scalars(
                    select(Event)
                    .where(Event.id > run.cursor_event_id)
                    .order_by(Event.id)
                    .limit(batch_size)
                )
            )
            if not events:
                run.status = "completed"
                run.finished_at = datetime.now(UTC).isoformat()
                run.message = "Prüflauf vollständig abgeschlossen."
                db.commit()
                return
            for event in events:
                run.cursor_event_id = event.id
                run.processed += 1
                if event.classification_status in {
                    "manual",
                    "learned",
                    "suggested",
                    "context_only",
                }:
                    continue
                mapped = base_class_for_detection(event.label, event.category)
                if mapped and mapped != event.primary_class_code:
                    event.primary_class_code = mapped
                    run.changed += 1
                    db.add(
                        EventClassificationRevision(
                            event_id=event.id,
                            primary_class_code=mapped,
                            subclass_code=event.subclass_code,
                            status="automatic",
                            actor=f"review:{run.kind}",
                            reason="Automatischer Prüflauf mit aktuellem Klassenkatalog",
                        )
                    )
            db.commit()


def pause_active_runs(db: Session) -> int:
    runs = list(db.scalars(select(ReviewRun).where(ReviewRun.status == "running")))
    for run in runs:
        run.status = "paused"
        run.message = "Prüflauf manuell unterbrochen."
    db.commit()
    return len(runs)


async def nightly_review_scheduler() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    while True:
        now = datetime.now(berlin)
        if now.hour == settings.nightly_review_hour:
            today = now.date().isoformat()
            with SessionLocal() as db:
                tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
            for tenant_id in tenant_ids:
                with SessionLocal() as db:
                    db.info["tenant_id"] = tenant_id
                    existing = db.scalar(
                        select(ReviewRun).where(
                            ReviewRun.kind == "nightly",
                            ReviewRun.created_at >= today,
                        )
                    )
                    active = db.scalar(
                        select(ReviewRun).where(ReviewRun.status.in_(("pending", "running")))
                    )
                    if existing is None and active is None:
                        run = ReviewRun(kind="nightly", status="pending", requested_by="scheduler")
                        db.add(run)
                        db.commit()
                        run_id = run.id
                    else:
                        run_id = None
                if run_id is not None:
                    await asyncio.to_thread(process_review_run, run_id)
        await asyncio.sleep(60)
