from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160), default="")
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[str | None] = mapped_column(String, nullable=True)


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_ip: Mapped[str] = mapped_column(String(64), default="")
    protocol_version: Mapped[int] = mapped_column(Integer, default=0)
    firmware_version: Mapped[str] = mapped_column(String(40), default="")
    sample_rate: Mapped[int] = mapped_column(Integer, default=0)
    uptime_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    packets_received: Mapped[int] = mapped_column(BigInteger, default=0)
    packets_lost: Mapped[int] = mapped_column(BigInteger, default=0)
    loss_rate: Mapped[float] = mapped_column(Float, default=0.0)
    peak: Mapped[int] = mapped_column(Integer, default=0)
    db_level: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen: Mapped[str] = mapped_column(String, default=utc_now)


class DeviceCalibration(Base):
    __tablename__ = "device_calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    low_reference_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_measured_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    medium_reference_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    medium_measured_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_reference_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_measured_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_offset_db: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class LiveAudioAccess(Base):
    __tablename__ = "live_audio_access"
    __table_args__ = (UniqueConstraint("user_id", "device_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class EventWitnessResponse(Base):
    __tablename__ = "event_witness_responses"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(80))
    response: Mapped[str] = mapped_column(String(20))
    responded_at: Mapped[str] = mapped_column(String, default=utc_now)


class EventClass(Base):
    __tablename__ = "event_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    level: Mapped[str] = mapped_column(String(20))
    parent_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    trainable: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(80), default="*")
    min_confidence: Mapped[float] = mapped_column(Float, default=0.7)
    min_db_level: Mapped[float] = mapped_column(Float, default=0.0)
    device: Mapped[str] = mapped_column(String(120), default="*")
    target: Mapped[str] = mapped_column(String(40), default="home_assistant")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=60)
    last_triggered_at: Mapped[str | None] = mapped_column(String, nullable=True)
