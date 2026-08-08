from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_roles
from app.database.session import get_db
from app.models.dashboard import (
    Device,
    DeviceCalibration,
    DeviceTelemetry,
    LiveAudioAccess,
    NotificationRule,
    User,
)
from app.models.event import Event
from app.schemas.dashboard import (
    CalibrationCapture,
    DeviceCalibrationRead,
    DeviceCreate,
    DeviceRead,
    DeviceTelemetryRead,
    DeviceUpdate,
    LiveAudioPermissionRead,
    LiveAudioPermissionUpdate,
    RuleCreate,
    RuleRead,
)
from app.services.calibration import calculate_recommended_offset

router = APIRouter(prefix="/api", tags=["Dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _events_since(db: Session, days: int, device: str | None = None) -> list[Event]:
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    statement = select(Event).where(Event.timestamp >= cutoff).order_by(Event.timestamp)
    if device:
        statement = statement.where(Event.device == device)
    return list(db.scalars(statement).all())


@router.get("/statistics")
def statistics(
    db: DatabaseSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=1, le=366),
    device: str | None = None,
) -> dict[str, object]:
    events = _events_since(db, days, device)
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
) -> list[dict[str, object]]:
    cells: dict[tuple[int, int], int] = defaultdict(int)
    for event in _events_since(db, days, device):
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
) -> list[dict[str, object]]:
    daily: dict[str, Counter[str]] = defaultdict(Counter)
    for event in _events_since(db, days, device):
        daily[event.timestamp[:10]][event.category] += 1
    return [
        {"date": date, "total": sum(values.values()), "categories": values}
        for date, values in sorted(daily.items())
    ]


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(db: DatabaseSession, _: CurrentUser) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.name)).all())


@router.get("/device-telemetry", response_model=list[DeviceTelemetryRead])
def list_device_telemetry(db: DatabaseSession, _: CurrentUser) -> list[DeviceTelemetry]:
    return list(db.scalars(select(DeviceTelemetry).order_by(DeviceTelemetry.device_id)).all())


@router.get("/device-calibrations", response_model=list[DeviceCalibrationRead])
def list_device_calibrations(db: DatabaseSession, _: CurrentUser) -> list[DeviceCalibration]:
    return list(db.scalars(select(DeviceCalibration).order_by(DeviceCalibration.device_id)).all())


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
        calibration.recommended_offset_db = calculate_recommended_offset(calibration)
        calibration.updated_at = now
        result.append(calibration)

    db.commit()
    for calibration in result:
        db.refresh(calibration)
    return result


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    data: DeviceCreate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> Device:
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
