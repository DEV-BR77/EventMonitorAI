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


class DeviceLevelSample(Base):
    __tablename__ = "device_level_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), index=True)
    timestamp: Mapped[str] = mapped_column(String, index=True)
    db_level: Mapped[float] = mapped_column(Float)


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
    applied_offset_db: Mapped[float] = mapped_column(Float, default=0.0)
    reference_points: Mapped[int] = mapped_column(Integer, default=0)
    reference_mae_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class CalibrationReferenceRun(Base):
    __tablename__ = "calibration_reference_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(240))
    started_at: Mapped[str] = mapped_column(String)
    ended_at: Mapped[str] = mapped_column(String)
    reference_points: Mapped[int] = mapped_column(Integer)
    tolerance_seconds: Mapped[float] = mapped_column(Float, default=3.0)
    created_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class CalibrationReferenceResult(Base):
    __tablename__ = "calibration_reference_results"
    __table_args__ = (UniqueConstraint("run_id", "device_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("calibration_reference_runs.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(120), index=True)
    matched_points: Mapped[int] = mapped_column(Integer)
    mean_reference_db: Mapped[float] = mapped_column(Float)
    mean_measured_db: Mapped[float] = mapped_column(Float)
    mean_difference_db: Mapped[float] = mapped_column(Float)
    mae_db: Mapped[float] = mapped_column(Float)
    recommended_offset_db: Mapped[float] = mapped_column(Float)


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
    hidden_by_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class IgnoredDetectionPattern(Base):
    __tablename__ = "ignored_detection_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_normalized: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    label_example: Mapped[str] = mapped_column(String(160))
    confirmations: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class EventClassificationRevision(Base):
    __tablename__ = "event_classification_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    primary_class_code: Mapped[str] = mapped_column(String(80))
    subclass_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class AudioClip(Base):
    __tablename__ = "audio_clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), index=True)
    trigger_id: Mapped[str] = mapped_column(String(64))
    trigger_uptime_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    received_at: Mapped[str] = mapped_column(String, index=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    path: Mapped[str] = mapped_column(Text)
    frame_count: Mapped[int] = mapped_column(Integer)
    sample_rate: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True
    )


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    cursor_event_id: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(String(500), default="")


class AssessmentConfig(Base):
    __tablename__ = "assessment_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sensitive_surcharge_db: Mapped[float] = mapped_column(Float, default=6.0)
    apply_to_live: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class PersonProfile(Base):
    __tablename__ = "person_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class EventPersonAssignment(Base):
    __tablename__ = "event_person_assignments"
    __table_args__ = (UniqueConstraint("event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(20), default="manual")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_at: Mapped[str] = mapped_column(String, default=utc_now)


class SpeakerCluster(Base):
    __tablename__ = "speaker_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    linked_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    centroid_json: Mapped[str] = mapped_column(Text)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    algorithm: Mapped[str] = mapped_column(String(80), default="voiceprint-v1")
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now)


class EventSpeakerCluster(Base):
    __tablename__ = "event_speaker_clusters"
    __table_args__ = (UniqueConstraint("event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("speaker_clusters.id", ondelete="CASCADE"), index=True
    )
    similarity: Mapped[float] = mapped_column(Float)
    assigned_at: Mapped[str] = mapped_column(String, default=utc_now)


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
