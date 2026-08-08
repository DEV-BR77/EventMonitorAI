from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Float, Integer, String
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
    last_seen: Mapped[str] = mapped_column(String, default=utc_now)


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
