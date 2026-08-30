import base64
import hashlib
import json
import secrets
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import Float, Numeric, case, cast, delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, hash_password, require_roles
from app.database.session import get_db
from app.models.dashboard import (
    AssessmentConfig,
    AdminNotification,
    AudioClip,
    CalibrationReferenceResult,
    CalibrationReferenceRun,
    Device,
    DeviceCalibration,
    DeviceCredential,
    DeviceLevelSample,
    DeviceTelemetry,
    EventClass,
    EventPersonAssignment,
    EventSpeakerCluster,
    LiveAudioAccess,
    NotificationRule,
    PersonProfile,
    SpeakerAnalysisRun,
    SpeakerCluster,
    Tenant,
    TenantMembership,
    TenantSubscription,
    User,
    WebsiteVisit,
)
from app.models.event import Event
from app.schemas.dashboard import (
    AssessmentConfigRead,
    AdminNotificationRead,
    AssessmentConfigWrite,
    CalibrationCapture,
    CalibrationOffsetApply,
    CalibrationOffsetSet,
    CalibrationReferenceImport,
    CalibrationReferenceResultRead,
    CalibrationReferenceRunRead,
    DeviceCalibrationRead,
    DeviceCreate,
    DeviceLevelPoint,
    DeviceRead,
    DeviceTelemetryRead,
    DeviceUpdate,
    DirectCalibrationCapture,
    EventClassRead,
    EventClassUpdate,
    EventClassWrite,
    LiveAudioPermissionRead,
    LiveAudioPermissionUpdate,
    PersonMediaUpload,
    PersonRead,
    PersonUpdate,
    PersonWrite,
    RuleCreate,
    RuleRead,
    SoundMapPoint,
    SpeakerAnalysisRunRead,
    SpeakerClusterUpdate,
    SpeakerSampleReview,
    TenantCreate,
)
from app.services.calibration import (
    calculate_recommended_offset,
    compare_reference_points,
    parse_reference_csv,
)
from app.services.noise_assessment import assessment_for
from app.services.person_media import store_photo, store_video_and_compare
from app.services.speaker_clustering import (
    create_cluster_from_event,
    link_cluster_to_person,
    recompute_cluster_centroid,
)

router = APIRouter(prefix="/api", tags=["Dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/admin-notifications", response_model=list[AdminNotificationRead])
def admin_notifications(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[AdminNotification]:
    return list(db.scalars(select(AdminNotification).where(AdminNotification.tenant_id == db.info["tenant_id"]).order_by(AdminNotification.id.desc()).limit(50)))


@router.post("/admin-notifications/{notification_id}/read", status_code=204)
def read_admin_notification(
    notification_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> None:
    notification = db.scalar(select(AdminNotification).where(AdminNotification.id == notification_id, AdminNotification.tenant_id == db.info["tenant_id"]))
    if notification is None:
        raise HTTPException(status_code=404, detail="Benachrichtigung nicht gefunden")
    notification.read_at = datetime.now(UTC).isoformat()
    db.commit()


@router.get("/account")
def account_summary(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    tenant_id = db.info["tenant_id"]
    tenant = db.get(Tenant, tenant_id)
    subscription = db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id))
    membership = db.scalar(select(TenantMembership).where(TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user.id))
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "role": membership.role,
        "plan": subscription.plan if subscription else "none",
        "subscription_status": subscription.status if subscription else "inactive",
        "max_devices": subscription.max_devices if subscription else 0,
        "retention_days": subscription.retention_days if subscription else 0,
        "device_count": db.scalar(select(func.count(Device.id))) or 0,
        "event_count": db.scalar(select(func.count(Event.id))) or 0,
    }


def _require_platform_admin(db: Session, user: User) -> None:
    if user.role != "admin" or db.info.get("tenant_id") != 1:
        raise HTTPException(status_code=403, detail="Nur die Plattformverwaltung darf Kundenbereiche verwalten")


@router.get("/platform/tenants")
def list_tenants(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    _require_platform_admin(db, user)
    tenants = list(db.scalars(select(Tenant).order_by(Tenant.id)))
    result = []
    for tenant in tenants:
        item = db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant.id))
        result.append({
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "active": tenant.active,
            "subscription": {"plan": item.plan, "status": item.status, "max_devices": item.max_devices, "retention_days": item.retention_days} if item else None,
        })
    return result


@router.get("/platform/website-visits")
def website_visits(
    db: DatabaseSession,
    user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, object]:
    _require_platform_admin(db, user)
    cutoff = (datetime.now(UTC) - timedelta(days=days - 1)).date().isoformat()
    rows = list(db.scalars(select(WebsiteVisit).where(WebsiteVisit.visit_date >= cutoff).order_by(WebsiteVisit.last_seen_at.desc())))
    return {
        "views": sum(item.views for item in rows),
        "visitors": len(rows),
        "days": [{"date": day, "views": sum(item.views for item in rows if item.visit_date == day), "visitors": sum(1 for item in rows if item.visit_date == day)} for day in sorted({item.visit_date for item in rows}, reverse=True)],
        "recent": [{"masked_ip": item.masked_ip, "views": item.views, "first_seen_at": item.first_seen_at, "last_seen_at": item.last_seen_at} for item in rows[:50]],
    }


@router.post("/platform/tenants", status_code=201)
def create_tenant(
    data: TenantCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    _require_platform_admin(db, user)
    if db.scalar(select(Tenant).where(Tenant.slug == data.slug)):
        raise HTTPException(status_code=409, detail="Kurzname des Kundenbereichs ist bereits vergeben")
    if db.scalar(select(User).where(func.lower(User.username) == data.admin_username.casefold())):
        raise HTTPException(status_code=409, detail="Benutzername ist bereits vergeben")
    tenant = Tenant(name=" ".join(data.name.split()), slug=data.slug)
    customer = User(username=data.admin_username.strip(), password_hash=hash_password(data.admin_password), role="admin")
    db.add_all([tenant, customer])
    db.flush()
    db.add_all([
        TenantMembership(tenant_id=tenant.id, user_id=customer.id, role="admin"),
        TenantSubscription(tenant_id=tenant.id, plan=data.plan, status="trialing", max_devices=data.max_devices, retention_days=data.retention_days),
    ])
    db.commit()
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "admin_username": customer.username}


@router.get("/support-config")
def support_config(_: CurrentUser) -> dict[str, str | bool | float]:
    url = settings.support_url.strip()
    target = max(0, settings.support_target_eur)
    collected = min(target, max(0, settings.support_collected_eur))
    return {
        "enabled": url.startswith("https://"),
        "url": url if url.startswith("https://") else "",
        "target_eur": target,
        "collected_eur": collected,
        "open_eur": target - collected,
        "progress": collected / target if target else 0,
    }


def _assessment_config(db: Session) -> AssessmentConfig:
    config = db.scalar(select(AssessmentConfig).order_by(AssessmentConfig.id))
    if config is None:
        config = AssessmentConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


DEFAULT_ASSESSMENT_CLASS_RULES = {
    "NO_NOISE": False,
    "WIND": False,
    "AMBIENT": False,
    "TECHNICAL": False,
}


def _assessment_class_rules(config: AssessmentConfig) -> dict[str, bool]:
    try:
        stored = json.loads(config.class_rules_json or "{}")
    except (TypeError, ValueError):
        stored = {}
    return {
        **DEFAULT_ASSESSMENT_CLASS_RULES,
        **{str(code): value for code, value in stored.items() if isinstance(value, bool)},
    }


def _event_is_assessment_included(event: Event, config: AssessmentConfig) -> bool:
    rules = _assessment_class_rules(config)
    if event.subclass_code in rules:
        return rules[event.subclass_code]
    if event.primary_class_code in rules:
        return rules[event.primary_class_code]
    return True


def _assessment_config_payload(config: AssessmentConfig) -> dict[str, object]:
    return {
        "sensitive_surcharge_db": config.sensitive_surcharge_db,
        "apply_to_live": config.apply_to_live,
        "class_rules": _assessment_class_rules(config),
        "updated_at": config.updated_at,
    }


def _events_since(
    db: Session,
    days: int,
    device: str | None = None,
    selected_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Event]:
    config = _assessment_config(db)
    if date_from or date_to:
        start = date_from or date_to
        end = date_to or date_from
        if start is None or end is None or start > end:
            raise HTTPException(status_code=422, detail="Ungültiger Datumsbereich")
        if (end - start).days > 366:
            raise HTTPException(
                status_code=422, detail="Der Zeitraum darf maximal 367 Tage umfassen"
            )
        statement = select(Event).where(
            Event.timestamp >= start.isoformat(),
            Event.timestamp < (end + timedelta(days=1)).isoformat(),
            Event.person_monitoring_excluded.is_(False),
            Event.assessment_excluded.is_(False),
        )
        if device:
            statement = statement.where(Event.device == device)
        return [event for event in db.scalars(statement.order_by(Event.timestamp)).all() if _event_is_assessment_included(event, config)]
    if selected_date is not None:
        prefix = selected_date.isoformat()
        statement = (
            select(Event)
            .where(
                Event.timestamp.like(f"{prefix}%"),
                Event.person_monitoring_excluded.is_(False),
                Event.assessment_excluded.is_(False),
            )
            .order_by(Event.timestamp)
        )
        if device:
            statement = statement.where(Event.device == device)
        return [event for event in db.scalars(statement).all() if _event_is_assessment_included(event, config)]
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    statement = (
        select(Event)
        .where(
            Event.timestamp >= cutoff,
            Event.person_monitoring_excluded.is_(False),
            Event.assessment_excluded.is_(False),
        )
        .order_by(Event.timestamp)
    )
    if device:
        statement = statement.where(Event.device == device)
    return [event for event in db.scalars(statement).all() if _event_is_assessment_included(event, config)]


@router.get("/statistics")
def statistics(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=366),
    device: str | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, object]:
    events = _events_since(db, days, device, date, date_from, date_to)
    categories = Counter(event.category for event in events)
    devices = Counter(event.device for event in events)
    return {
        "total": len(events),
        "average_db": round(sum(e.db_level for e in events) / len(events), 1) if events else 0,
        "max_db": max((e.db_level for e in events), default=0),
        "average_confidence": (
            round(sum(e.confidence for e in events) / len(events), 3) if events else 0
        ),
        "categories": categories,
        "devices": devices,
    }


@router.get("/heatmap")
def heatmap(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=366),
    device: str | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, object]]:
    cells: dict[tuple[int, int], int] = defaultdict(int)
    for event in _events_since(db, days, device, date, date_from, date_to):
        try:
            value = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        cells[(value.weekday(), value.hour)] += 1
    return [
        {"weekday": weekday, "hour": hour, "count": count}
        for (weekday, hour), count in sorted(cells.items())
    ]


@router.get("/calendar")
def calendar(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=366),
    device: str | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, object]]:
    daily: dict[str, Counter[str]] = defaultdict(Counter)
    config = _assessment_config(db)
    for event in _events_since(db, days, device, date, date_from, date_to):
        values = daily[event.timestamp[:10]]
        values[event.category] += 1
        if assessment_for(
            event.timestamp,
            event.db_level,
            config.sensitive_surcharge_db,
            config.apply_to_live,
        )["exceeded"]:
            values["__exceeded__"] += 1
    return [
        {
            "date": day,
            "total": sum(value for key, value in values.items() if key != "__exceeded__"),
            "exceeded": values["__exceeded__"],
            "categories": {key: value for key, value in values.items() if key != "__exceeded__"},
        }
        for day, values in sorted(daily.items())
    ]


@router.get("/kpis")
def noise_kpis(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=366),
    device: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, object]:
    events = _events_since(db, days, device, None, date_from, date_to)
    config = _assessment_config(db)
    exceeded = [
        event
        for event in events
        if assessment_for(
            event.timestamp,
            event.db_level,
            config.sensitive_surcharge_db,
            config.apply_to_live,
        )["exceeded"]
    ]
    levels = sorted(event.db_level for event in events)
    percentile_index = (
        max(0, min(len(levels) - 1, round((len(levels) - 1) * 0.95))) if levels else 0
    )
    daily: dict[str, list[Event]] = defaultdict(list)
    hourly = Counter()
    for event in events:
        daily[event.timestamp[:10]].append(event)
        try:
            hourly[datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")).hour] += 1
        except ValueError:
            pass
    top_hour = hourly.most_common(1)[0] if hourly else (None, 0)
    return {
        "total": len(events),
        "exceeded": len(exceeded),
        "exceeded_rate": round(len(exceeded) / len(events), 4) if events else 0,
        "average_db": round(sum(levels) / len(levels), 1) if levels else 0,
        "maximum_db": round(max(levels), 1) if levels else 0,
        "p95_db": round(levels[percentile_index], 1) if levels else 0,
        "total_duration_seconds": round(sum(event.duration_seconds for event in events), 1),
        "top_hour": top_hour[0],
        "top_hour_events": top_hour[1],
        "categories": dict(Counter(event.category for event in events).most_common(10)),
        "labels": dict(Counter(event.label_de or event.label for event in events).most_common(10)),
        "devices": dict(Counter(event.device for event in events)),
        "hours": [{"hour": hour, "count": hourly[hour]} for hour in range(24)],
        "daily": [
            {
                "date": day,
                "total": len(values),
                "exceeded": sum(value in exceeded for value in values),
                "average_db": round(sum(value.db_level for value in values) / len(values), 1),
                "maximum_db": round(max(value.db_level for value in values), 1),
            }
            for day, values in sorted(daily.items())
        ],
    }


@router.get("/assessment-config", response_model=AssessmentConfigRead)
def get_assessment_config(db: DatabaseSession, _: CurrentUser) -> dict[str, object]:
    return _assessment_config_payload(_assessment_config(db))


@router.put("/assessment-config", response_model=AssessmentConfigRead)
def update_assessment_config(
    data: AssessmentConfigWrite,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, object]:
    config = _assessment_config(db)
    config.sensitive_surcharge_db = data.sensitive_surcharge_db
    config.apply_to_live = data.apply_to_live
    valid_codes = set(db.scalars(select(EventClass.code)).all())
    config.class_rules_json = json.dumps(
        {code: included for code, included in data.class_rules.items() if code in valid_codes},
        sort_keys=True,
    )
    config.updated_at = datetime.now(UTC).isoformat()
    db.commit()
    db.refresh(config)
    return _assessment_config_payload(config)


@router.get("/people", response_model=list[PersonRead])
def list_people(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[PersonRead]:
    people = list(db.scalars(select(PersonProfile).order_by(PersonProfile.name)))
    assignments = list(db.scalars(select(EventPersonAssignment)))
    events = {
        event.id: event
        for event in db.scalars(
            select(Event).where(Event.id.in_({item.event_id for item in assignments}))
        )
    }
    by_person: dict[int, list[Event]] = defaultdict(list)
    cluster_names = {item.id: item.name for item in db.scalars(select(SpeakerCluster))}
    for assignment in assignments:
        if assignment.confirmed and assignment.event_id in events:
            by_person[assignment.person_id].append(events[assignment.event_id])
    return [
        PersonRead(
            id=person.id,
            name=person.name,
            active=person.active,
            monitoring_enabled=person.monitoring_enabled,
            created_at=person.created_at,
            updated_at=person.updated_at,
            frequency=len(by_person[person.id]),
            total_duration_seconds=round(
                sum(event.duration_seconds for event in by_person[person.id]), 1
            ),
            categories=dict(Counter(event.category for event in by_person[person.id])),
            photo_available=bool(person.photo_path),
            video_available=bool(person.video_path),
            video_audio_available=bool(person.video_audio_path),
            video_voice_similarity=person.video_voice_similarity,
            video_voice_cluster_id=person.video_voice_cluster_id,
            video_voice_cluster_name=cluster_names.get(person.video_voice_cluster_id),
        )
        for person in people
    ]


@router.post("/people", response_model=PersonRead, status_code=201)
def create_person(
    data: PersonWrite,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> PersonRead:
    name = " ".join(data.name.split())
    if db.scalar(select(PersonProfile).where(PersonProfile.name == name)):
        raise HTTPException(status_code=409, detail="Personenname existiert bereits")
    person = PersonProfile(
        name=name,
        active=data.active,
        monitoring_enabled=data.monitoring_enabled,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return PersonRead.model_validate(person, from_attributes=True)


@router.patch("/people/{person_id}", status_code=204)
def update_person(
    person_id: int,
    data: PersonUpdate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> None:
    person = db.get(PersonProfile, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Personenprofil nicht gefunden")
    name = " ".join(data.name.split())
    duplicate = db.scalar(
        select(PersonProfile).where(PersonProfile.name == name, PersonProfile.id != person.id)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Personenname existiert bereits")
    person.name = name
    person.active = data.active
    person.monitoring_enabled = data.monitoring_enabled
    person.updated_at = datetime.now(UTC).isoformat()
    event_ids = set(
        db.scalars(
            select(EventPersonAssignment.event_id).where(
                EventPersonAssignment.person_id == person.id,
                EventPersonAssignment.confirmed.is_(True),
            )
        )
    )
    if event_ids:
        for event in db.scalars(select(Event).where(Event.id.in_(event_ids))):
            event.person_monitoring_excluded = not person.monitoring_enabled
    db.commit()


def _person_media_file(person: PersonProfile, kind: str) -> FileResponse:
    path_value = {
        "photo": person.photo_path,
        "video": person.video_path,
        "voice": person.video_audio_path,
    }[kind]
    if not path_value:
        raise HTTPException(status_code=404, detail="Medium nicht vorhanden")
    root = Path(settings.person_media_directory).resolve()
    path = Path(path_value).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Mediendatei nicht gefunden")
    media_type = {
        "photo": "image/png" if path.suffix.lower() == ".png" else "image/jpeg",
        "video": {".webm": "video/webm", ".mov": "video/quicktime"}.get(path.suffix.lower(), "video/mp4"),
        "voice": "audio/wav",
    }[kind]
    return FileResponse(path, media_type=media_type)


@router.post("/people/{person_id}/media")
def upload_person_media(
    person_id: int,
    data: PersonMediaUpload,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, object]:
    person = db.get(PersonProfile, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Personenprofil nicht gefunden")
    try:
        if data.media_type == "photo":
            store_photo(person, data.content_base64, data.mime_type)
            result: dict[str, object] = {"message": "Profilbild gespeichert"}
        else:
            result = store_video_and_compare(db, person, data.content_base64, data.mime_type)
    except (OSError, ValueError, TimeoutError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    person.updated_at = datetime.now(UTC).isoformat()
    db.commit()
    return result


@router.get("/people/{person_id}/media/{kind}")
def person_media(
    person_id: int,
    kind: str,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> FileResponse:
    if kind not in {"photo", "video", "voice"}:
        raise HTTPException(status_code=404, detail="Unbekannter Medientyp")
    person = db.get(PersonProfile, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Personenprofil nicht gefunden")
    return _person_media_file(person, kind)


@router.get("/speaker-clusters")
def list_speaker_clusters(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[dict[str, object]]:
    people = {item.id: item.name for item in db.scalars(select(PersonProfile))}
    clusters = list(db.scalars(select(SpeakerCluster).order_by(SpeakerCluster.id)))
    ecapa_clusters = [item for item in clusters if item.algorithm == "speechbrain-ecapa-voxceleb"]
    if ecapa_clusters:
        clusters = ecapa_clusters
    result = []
    for cluster in clusters:
        assignments = list(
            db.scalars(
                select(EventSpeakerCluster).where(EventSpeakerCluster.cluster_id == cluster.id)
            )
        )
        event_ids = [item.event_id for item in assignments]
        status_counts = Counter(item.review_status for item in assignments)
        events = list(db.scalars(select(Event).where(Event.id.in_(event_ids)))) if event_ids else []
        result.append(
            {
                "id": cluster.id,
                "name": cluster.name,
                "person_id": cluster.linked_person_id,
                "person_name": people.get(cluster.linked_person_id),
                "sample_count": len(assignments),
                "pending_count": status_counts["pending"],
                "confirmed_count": status_counts["confirmed"],
                "rejected_count": status_counts["rejected"] + status_counts["no_voice"],
                "average_similarity": (
                    round(sum(item.similarity for item in assignments) / len(assignments), 3)
                    if assignments
                    else 0
                ),
                "first_seen": min((item.timestamp for item in events), default=None),
                "last_seen": max((item.timestamp for item in events), default=None),
                "algorithm": cluster.algorithm,
            }
        )
    return result


@router.post(
    "/speaker-analysis/runs",
    response_model=SpeakerAnalysisRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_speaker_analysis_run(
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin"))],
) -> SpeakerAnalysisRun:
    active = db.scalar(
        select(SpeakerAnalysisRun).where(SpeakerAnalysisRun.status.in_(("pending", "running")))
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Eine Stimmanalyse läuft bereits")
    run = SpeakerAnalysisRun(status="pending", requested_by=user.username, message="Analyse wartet auf den Hintergrund-Worker.")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/speaker-analysis/runs/latest", response_model=SpeakerAnalysisRunRead | None)
def latest_speaker_analysis_run(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> SpeakerAnalysisRun | None:
    return db.scalar(select(SpeakerAnalysisRun).order_by(SpeakerAnalysisRun.id.desc()).limit(1))


@router.patch("/speaker-clusters/{cluster_id}")
def update_speaker_cluster(
    cluster_id: int,
    data: SpeakerClusterUpdate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, object]:
    cluster = db.get(SpeakerCluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Stimmgruppe nicht gefunden")
    if data.name is not None:
        name = " ".join(data.name.split())
        duplicate = db.scalar(
            select(SpeakerCluster).where(
                SpeakerCluster.name == name, SpeakerCluster.id != cluster.id
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Name der Stimmgruppe existiert bereits")
        cluster.name = name
    if "person_id" in data.model_fields_set:
        person = None
        if data.person_id is not None:
            person = db.get(PersonProfile, data.person_id)
            if person is None or not person.active:
                raise HTTPException(status_code=422, detail="Person nicht gefunden oder inaktiv")
        link_cluster_to_person(db, cluster, person)
    else:
        cluster.updated_at = datetime.now(UTC).isoformat()
        db.commit()
    return {"id": cluster.id, "name": cluster.name, "person_id": cluster.linked_person_id}


@router.get("/speaker-clusters/{cluster_id}/samples")
def list_speaker_cluster_samples(
    cluster_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
    review_status: str = Query(default="pending", pattern="^(pending|confirmed|rejected|no_voice|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    cluster = db.get(SpeakerCluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Stimmgruppe nicht gefunden")
    statement = (
        select(EventSpeakerCluster, Event, AudioClip)
        .join(Event, Event.id == EventSpeakerCluster.event_id)
        .outerjoin(AudioClip, AudioClip.event_id == Event.id)
        .where(EventSpeakerCluster.cluster_id == cluster_id)
    )
    if review_status != "all":
        statement = statement.where(EventSpeakerCluster.review_status == review_status)
    rows = db.execute(statement.order_by(Event.timestamp.desc())).all()
    items = [
        {
            "event_id": assignment.event_id,
            "similarity": round(assignment.similarity, 4),
            "review_status": assignment.review_status,
            "reviewed_by": assignment.reviewed_by,
            "reviewed_at": assignment.reviewed_at,
            "timestamp": event.timestamp,
            "label": event.label_de or event.label,
            "device": event.device,
            "db_level": event.db_level,
            "audio_available": clip is not None,
        }
        for assignment, event, clip in rows[offset : offset + limit]
    ]
    return {"cluster_id": cluster_id, "total": len(rows), "offset": offset, "items": items}


@router.patch("/speaker-clusters/{cluster_id}/samples/{event_id}")
def review_speaker_cluster_sample(
    cluster_id: int,
    event_id: int,
    data: SpeakerSampleReview,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, object]:
    cluster = db.get(SpeakerCluster, cluster_id)
    assignment = db.scalar(
        select(EventSpeakerCluster).where(
            EventSpeakerCluster.cluster_id == cluster_id,
            EventSpeakerCluster.event_id == event_id,
        )
    )
    if cluster is None or assignment is None:
        raise HTTPException(status_code=404, detail="Aufnahme in dieser Stimmgruppe nicht gefunden")

    target = cluster
    new_status = {
        "confirm": "confirmed",
        "reject": "rejected",
        "no_voice": "no_voice",
        "move": "pending",
        "new_cluster": "confirmed",
    }[data.action]
    if data.action == "move":
        if data.target_cluster_id is None or data.target_cluster_id == cluster_id:
            raise HTTPException(status_code=422, detail="Bitte eine andere Zielgruppe auswählen")
        target = db.get(SpeakerCluster, data.target_cluster_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Zielgruppe nicht gefunden")
        assignment.cluster_id = target.id
    elif data.action == "new_cluster":
        try:
            target = create_cluster_from_event(db, event_id)
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        assignment.cluster_id = target.id

    person_assignment = db.scalar(
        select(EventPersonAssignment).where(
            EventPersonAssignment.event_id == event_id,
            EventPersonAssignment.source == "speaker_cluster",
        )
    )
    if person_assignment is not None:
        db.delete(person_assignment)
        event = db.get(Event, event_id)
        if event is not None:
            event.person_monitoring_excluded = False
    assignment.review_status = new_status
    assignment.reviewed_by = user.username
    assignment.reviewed_at = datetime.now(UTC).isoformat()
    recompute_cluster_centroid(db, cluster)
    if target.id != cluster.id:
        recompute_cluster_centroid(db, target)
    db.commit()
    if target.linked_person_id is not None and new_status == "confirmed":
        person = db.get(PersonProfile, target.linked_person_id)
        link_cluster_to_person(db, target, person)
    return {
        "event_id": event_id,
        "cluster_id": target.id,
        "review_status": new_status,
    }


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(db: DatabaseSession, _: CurrentUser) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.name)).all())


@router.get("/device-telemetry", response_model=list[DeviceTelemetryRead])
def list_device_telemetry(db: DatabaseSession, _: CurrentUser) -> list[DeviceTelemetry]:
    return list(db.scalars(select(DeviceTelemetry).order_by(DeviceTelemetry.device_id)).all())


@router.get("/device-levels", response_model=list[DeviceLevelPoint])
def device_levels(
    db: DatabaseSession,
    _: CurrentUser,
    minutes: int = Query(default=10),
    device: str | None = None,
) -> list[DeviceLevelPoint]:
    if minutes not in {5, 10, 30, 60}:
        raise HTTPException(status_code=422, detail="Erlaubt sind 5, 10, 30 oder 60 Minuten")
    cutoff = (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()
    statement = select(DeviceLevelSample).where(DeviceLevelSample.timestamp >= cutoff)
    if device:
        statement = statement.where(DeviceLevelSample.device_id == device)
    samples = list(db.scalars(statement.order_by(DeviceLevelSample.timestamp)))
    names = {
        item.device_id: item.name
        for item in db.scalars(select(Device).where(Device.enabled.is_(True)))
    }
    buckets: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for sample in samples:
        if sample.device_id in names:
            instant = datetime.fromisoformat(sample.timestamp.replace("Z", "+00:00"))
            bucket_second = instant.second - instant.second % 5
            bucket = instant.replace(second=bucket_second, microsecond=0).isoformat()
            buckets[(sample.device_id, bucket)].append((sample.timestamp, sample.db_level))
    return [
        DeviceLevelPoint(
            device_id=device_id,
            name=names[device_id],
            timestamp=bucket,
            average_db=round(sum(level for _, level in levels) / len(levels), 1),
            maximum_db=round(max(level for _, level in levels), 1),
        )
        for (device_id, bucket), levels in sorted(buckets.items(), key=lambda item: item[0][1])
    ]


@router.get("/sound-map", response_model=list[SoundMapPoint])
def sound_map(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
    threshold_db: float = Query(default=55, ge=0, le=140),
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[SoundMapPoint]:
    devices = list(db.scalars(select(Device).where(Device.enabled.is_(True)).order_by(Device.name)))
    events = _events_since(db, days, None, None, date_from, date_to)
    telemetry = {item.device_id: item for item in db.scalars(select(DeviceTelemetry)).all()}
    points: list[SoundMapPoint] = []
    for device in devices:
        device_events = [event for event in events if event.device == device.device_id]
        levels = [event.db_level for event in device_events]
        current = telemetry.get(device.device_id)
        points.append(
            SoundMapPoint(
                device_id=device.device_id,
                name=device.name,
                location=device.location,
                position_x=device.position_x,
                position_y=device.position_y,
                current_db=current.db_level if current else None,
                average_db=round(sum(levels) / len(levels), 1) if levels else None,
                maximum_db=round(max(levels), 1) if levels else None,
                exceedances=sum(level >= threshold_db for level in levels),
            )
        )
    return points


@router.get("/device-calibrations", response_model=list[DeviceCalibrationRead])
def list_device_calibrations(db: DatabaseSession, _: CurrentUser) -> list[DeviceCalibration]:
    return list(db.scalars(select(DeviceCalibration).order_by(DeviceCalibration.device_id)).all())


@router.post("/device-calibrations/direct", response_model=DeviceCalibrationRead)
def apply_direct_device_calibration(
    data: DirectCalibrationCapture,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin"))],
) -> DeviceCalibration:
    telemetry = db.scalar(
        select(DeviceTelemetry).where(DeviceTelemetry.device_id == data.device_id)
    )
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Für dieses Mikrofon liegt kein Messwert vor")
    last_seen = datetime.fromisoformat(telemetry.last_seen.replace("Z", "+00:00"))
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if datetime.now(UTC) - last_seen.astimezone(UTC) > timedelta(seconds=15):
        raise HTTPException(status_code=409, detail="Der Mikrofonwert ist älter als 15 Sekunden")
    calibration = db.scalar(
        select(DeviceCalibration).where(DeviceCalibration.device_id == data.device_id)
    )
    if calibration is None:
        calibration = DeviceCalibration(device_id=data.device_id)
        db.add(calibration)
    measured_db = telemetry.db_level
    setattr(calibration, f"{data.level}_reference_db", data.reference_db)
    setattr(calibration, f"{data.level}_measured_db", measured_db)
    calibration.recommended_offset_db = round(
        max(-30.0, min(30.0, calibration.applied_offset_db + data.reference_db - measured_db)),
        2,
    )
    calibration.updated_at = datetime.now(UTC).isoformat()
    db.flush()
    return apply_calibration_offsets(
        CalibrationOffsetApply(device_ids=[data.device_id]), db, user
    )[0]


@router.post("/device-calibrations/set-offset", response_model=DeviceCalibrationRead)
def set_device_calibration_offset(
    data: CalibrationOffsetSet,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin"))],
) -> DeviceCalibration:
    calibration = db.scalar(
        select(DeviceCalibration).where(DeviceCalibration.device_id == data.device_id)
    )
    if calibration is None:
        calibration = DeviceCalibration(device_id=data.device_id)
        db.add(calibration)
    calibration.recommended_offset_db = round(data.target_offset_db, 2)
    calibration.updated_at = datetime.now(UTC).isoformat()
    db.flush()
    return apply_calibration_offsets(
        CalibrationOffsetApply(device_ids=[data.device_id]), db, user
    )[0]


@router.post("/device-calibrations/capture", response_model=list[DeviceCalibrationRead])
def capture_device_calibration(
    data: CalibrationCapture,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> list[DeviceCalibration]:
    telemetry_by_device = {
        item.device_id: item
        for item in db.scalars(
            select(DeviceTelemetry).where(DeviceTelemetry.device_id.in_(data.device_ids))
        ).all()
    }
    missing = sorted(set(data.device_ids) - telemetry_by_device.keys())
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"Keine Telemetrie für: {', '.join(missing)}",
        )

    result: list[DeviceCalibration] = []
    now = datetime.now(UTC).isoformat()
    for device_id in data.device_ids:
        calibration = db.scalar(
            select(DeviceCalibration).where(DeviceCalibration.device_id == device_id)
        )
        if calibration is None:
            calibration = DeviceCalibration(device_id=device_id)
            db.add(calibration)
        setattr(calibration, f"{data.level}_reference_db", data.reference_db)
        setattr(calibration, f"{data.level}_measured_db", telemetry_by_device[device_id].db_level)
        calibration.recommended_offset_db = round(
            calibration.applied_offset_db + calculate_recommended_offset(calibration), 2
        )
        calibration.updated_at = now
        result.append(calibration)

    db.commit()
    for calibration in result:
        db.refresh(calibration)
    return result


def _reference_run_read(
    run: CalibrationReferenceRun,
    results: list[CalibrationReferenceResult],
) -> CalibrationReferenceRunRead:
    return CalibrationReferenceRunRead(
        id=run.id,
        filename=run.filename,
        started_at=run.started_at,
        ended_at=run.ended_at,
        reference_points=run.reference_points,
        tolerance_seconds=run.tolerance_seconds,
        created_by=run.created_by,
        created_at=run.created_at,
        results=[
            CalibrationReferenceResultRead(
                device_id=item.device_id,
                matched_points=item.matched_points,
                mean_reference_db=item.mean_reference_db,
                mean_measured_db=item.mean_measured_db,
                mean_difference_db=item.mean_difference_db,
                mae_db=item.mae_db,
                recommended_offset_db=item.recommended_offset_db,
            )
            for item in results
        ],
    )


@router.get(
    "/device-calibrations/reference-runs",
    response_model=list[CalibrationReferenceRunRead],
)
def list_calibration_reference_runs(
    db: DatabaseSession,
    _: CurrentUser,
) -> list[CalibrationReferenceRunRead]:
    runs = list(
        db.scalars(
            select(CalibrationReferenceRun).order_by(CalibrationReferenceRun.id.desc())
        ).all()
    )
    return [
        _reference_run_read(
            run,
            list(
                db.scalars(
                    select(CalibrationReferenceResult)
                    .where(CalibrationReferenceResult.run_id == run.id)
                    .order_by(CalibrationReferenceResult.device_id)
                ).all()
            ),
        )
        for run in runs
    ]


@router.post(
    "/device-calibrations/reference-import",
    response_model=CalibrationReferenceRunRead,
    status_code=status.HTTP_201_CREATED,
)
def import_calibration_reference(
    data: CalibrationReferenceImport,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> CalibrationReferenceRunRead:
    try:
        payload = base64.b64decode(data.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="CSV-Inhalt ist ungültig") from exc
    if len(payload) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV darf höchstens 2 MB groß sein")
    try:
        reference = parse_reference_csv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    device_ids = sorted(set(data.device_ids))
    known = set(db.scalars(select(Device.device_id).where(Device.device_id.in_(device_ids))).all())
    missing = sorted(set(device_ids) - known)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unbekannte Mikrofone: {', '.join(missing)}")
    start = reference[0][0].isoformat()
    end = reference[-1][0].isoformat()
    run = CalibrationReferenceRun(
        filename=data.filename,
        started_at=start,
        ended_at=end,
        reference_points=len(reference),
        tolerance_seconds=data.tolerance_seconds,
        created_by=user.username,
    )
    db.add(run)
    db.flush()
    results: list[CalibrationReferenceResult] = []
    now = datetime.now(UTC).isoformat()
    for device_id in device_ids:
        samples = list(
            db.scalars(
                select(DeviceLevelSample)
                .where(
                    DeviceLevelSample.device_id == device_id,
                    DeviceLevelSample.timestamp >= start,
                    DeviceLevelSample.timestamp <= end,
                )
                .order_by(DeviceLevelSample.timestamp)
            ).all()
        )
        calibration = db.scalar(
            select(DeviceCalibration).where(DeviceCalibration.device_id == device_id)
        )
        if calibration is None:
            calibration = DeviceCalibration(device_id=device_id)
            db.add(calibration)
            db.flush()
        try:
            comparison = compare_reference_points(
                samples,
                reference,
                data.tolerance_seconds,
                calibration.applied_offset_db,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{device_id}: {exc}") from exc
        result = CalibrationReferenceResult(run_id=run.id, device_id=device_id, **comparison)
        db.add(result)
        results.append(result)
        calibration.recommended_offset_db = float(comparison["recommended_offset_db"])
        calibration.reference_points = int(comparison["matched_points"])
        calibration.reference_mae_db = float(comparison["mae_db"])
        calibration.updated_at = now
    db.commit()
    db.refresh(run)
    for result in results:
        db.refresh(result)
    return _reference_run_read(run, results)


def _rounded_db(expression):
    return cast(func.round(cast(expression, Numeric), 2), Float)


@router.post(
    "/device-calibrations/apply-offsets",
    response_model=list[DeviceCalibrationRead],
)
def apply_calibration_offsets(
    data: CalibrationOffsetApply,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[DeviceCalibration]:
    calibrations = list(
        db.scalars(
            select(DeviceCalibration).where(DeviceCalibration.device_id.in_(data.device_ids))
        ).all()
    )
    missing = sorted(set(data.device_ids) - {item.device_id for item in calibrations})
    if missing:
        raise HTTPException(status_code=422, detail=f"Keine Kalibrierung für: {', '.join(missing)}")
    now = datetime.now(UTC).isoformat()
    for calibration in calibrations:
        offset_delta = round(
            calibration.recommended_offset_db - calibration.applied_offset_db,
            2,
        )
        if offset_delta:
            tenant_id = db.info.get("tenant_id", 1)
            event_level = Event.db_level + offset_delta
            event_average = Event.avg_db_level + offset_delta
            sample_level = DeviceLevelSample.db_level + offset_delta
            rounded_event_level = _rounded_db(event_level)
            rounded_event_average = _rounded_db(event_average)
            rounded_sample_level = _rounded_db(sample_level)
            db.execute(
                update(Event)
                .where(Event.tenant_id == tenant_id, Event.device == calibration.device_id)
                .values(
                    db_level=case(
                        (event_level < 0, 0.0), else_=rounded_event_level
                    ),
                    avg_db_level=case(
                        (Event.avg_db_level.is_(None), None),
                        (event_average < 0, 0.0),
                        else_=rounded_event_average,
                    ),
                )
                .execution_options(synchronize_session=False)
            )
            db.execute(
                update(DeviceLevelSample)
                .where(
                    DeviceLevelSample.tenant_id == tenant_id,
                    DeviceLevelSample.device_id == calibration.device_id,
                )
                .values(
                    db_level=case(
                        (sample_level < 0, 0.0), else_=rounded_sample_level
                    )
                )
                .execution_options(synchronize_session=False)
            )
            db.expire_all()
            telemetry = db.scalar(
                select(DeviceTelemetry).where(DeviceTelemetry.device_id == calibration.device_id)
            )
            if telemetry is not None:
                telemetry.db_level = round(max(0.0, telemetry.db_level + offset_delta), 2)
        calibration.applied_offset_db = calibration.recommended_offset_db
        calibration.updated_at = now
    db.commit()
    for calibration in calibrations:
        db.refresh(calibration)
    return calibrations


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    data: DeviceCreate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> Device:
    subscription = db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == db.info["tenant_id"]))
    device_count = db.scalar(select(func.count(Device.id))) or 0
    if subscription is None or subscription.status not in {"active", "trialing"}:
        raise HTTPException(status_code=402, detail="Für neue Mikrofone ist ein aktives Abonnement erforderlich")
    if device_count >= subscription.max_devices:
        raise HTTPException(status_code=409, detail="Gerätelimit des Tarifs erreicht")
    if db.scalar(select(Device).where(Device.device_id == data.device_id)):
        raise HTTPException(status_code=409, detail="Device already exists")
    device = Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.patch("/devices/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: str,
    data: DeviceUpdate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> Device:
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Mikrofon nicht gefunden")
    for field, value in data.model_dump().items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


@router.post("/devices/{device_id}/credential")
def rotate_device_credential(
    device_id: str,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, str]:
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Mikrofon nicht gefunden")
    secret = secrets.token_urlsafe(32)
    digest = hashlib.sha256(secret.encode()).hexdigest()
    credential = db.scalar(select(DeviceCredential).where(DeviceCredential.device_id == device_id))
    if credential is None:
        credential = DeviceCredential(tenant_id=db.info["tenant_id"], device_id=device_id, secret_hash=digest)
        db.add(credential)
    else:
        if credential.tenant_id != db.info["tenant_id"]:
            raise HTTPException(status_code=403, detail="Mikrofon gehört zu einem anderen Kundenbereich")
        credential.secret_hash = digest
        credential.active = True
    db.commit()
    return {"device_id": device_id, "secret": secret, "note": "Dieses Gerätegeheimnis wird nur einmal angezeigt"}


def _audio_permission(db: Session, user: User) -> LiveAudioPermissionRead:
    device_ids = list(
        db.scalars(
            select(LiveAudioAccess.device_id)
            .where(LiveAudioAccess.user_id == user.id)
            .order_by(LiveAudioAccess.device_id)
        ).all()
    )
    return LiveAudioPermissionRead(
        user_id=user.id,
        username=user.username,
        role=user.role,
        device_ids=device_ids,
    )


@router.get("/live-audio/devices", response_model=list[DeviceRead])
def live_audio_devices(db: DatabaseSession, user: CurrentUser) -> list[Device]:
    statement = select(Device).where(Device.enabled.is_(True)).order_by(Device.name)
    if user.role != "admin":
        statement = statement.join(
            LiveAudioAccess,
            LiveAudioAccess.device_id == Device.device_id,
        ).where(LiveAudioAccess.user_id == user.id)
    return list(db.scalars(statement).all())


@router.get("/live-audio/permissions", response_model=list[LiveAudioPermissionRead])
def list_live_audio_permissions(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[LiveAudioPermissionRead]:
    users = db.scalars(select(User).where(User.role != "admin").order_by(User.username))
    return [_audio_permission(db, user) for user in users]


@router.put("/live-audio/permissions/{user_id}", response_model=LiveAudioPermissionRead)
def update_live_audio_permission(
    user_id: int,
    data: LiveAudioPermissionUpdate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> LiveAudioPermissionRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    device_ids = sorted(set(data.device_ids))
    known_ids = set(
        db.scalars(select(Device.device_id).where(Device.device_id.in_(device_ids))).all()
    )
    missing = sorted(set(device_ids) - known_ids)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unbekannte Mikrofone: {', '.join(missing)}")
    db.execute(delete(LiveAudioAccess).where(LiveAudioAccess.user_id == user_id))
    db.add_all(LiveAudioAccess(user_id=user_id, device_id=item) for item in device_ids)
    db.commit()
    return _audio_permission(db, user)


def _validate_event_class_parent(
    db: Session,
    level: str,
    parent_code: str | None,
) -> None:
    if level == "base" and parent_code is not None:
        raise HTTPException(status_code=422, detail="Basisklassen dürfen keine Elternklasse haben")
    if parent_code is None:
        return
    parent = db.scalar(select(EventClass).where(EventClass.code == parent_code))
    if parent is None or parent.level != "base":
        raise HTTPException(status_code=422, detail="Elternklasse muss eine Basisklasse sein")


@router.get("/event-classes", response_model=list[EventClassRead])
def list_event_classes(db: DatabaseSession, _: CurrentUser) -> list[EventClass]:
    return list(db.scalars(select(EventClass).order_by(EventClass.sort_order, EventClass.name)))


@router.post("/event-classes", response_model=EventClassRead, status_code=status.HTTP_201_CREATED)
def create_event_class(
    data: EventClassWrite,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> EventClass:
    if db.scalar(
        select(EventClass).where((EventClass.code == data.code) | (EventClass.name == data.name))
    ):
        raise HTTPException(status_code=409, detail="Code oder Klassenname ist bereits vorhanden")
    _validate_event_class_parent(db, data.level, data.parent_code)
    event_class = EventClass(**data.model_dump())
    db.add(event_class)
    db.commit()
    db.refresh(event_class)
    return event_class


@router.patch("/event-classes/{class_id}", response_model=EventClassRead)
def update_event_class(
    class_id: int,
    data: EventClassUpdate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> EventClass:
    event_class = db.get(EventClass, class_id)
    if event_class is None:
        raise HTTPException(status_code=404, detail="Ereignisklasse nicht gefunden")
    duplicate = db.scalar(
        select(EventClass).where(EventClass.name == data.name, EventClass.id != class_id)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Klassenname ist bereits vorhanden")
    _validate_event_class_parent(db, data.level, data.parent_code)
    for field, value in data.model_dump().items():
        setattr(event_class, field, value)
    event_class.updated_at = datetime.now(UTC).isoformat()
    db.commit()
    db.refresh(event_class)
    return event_class


@router.get("/notification-rules", response_model=list[RuleRead])
def list_rules(db: DatabaseSession, _: CurrentUser) -> list[NotificationRule]:
    return list(db.scalars(select(NotificationRule).order_by(NotificationRule.name)).all())


@router.post("/notification-rules", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    data: RuleCreate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> NotificationRule:
    rule = NotificationRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/notification-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> None:
    rule = db.get(NotificationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
