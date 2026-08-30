from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class RegistrationRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=256)


class AdminNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    message: str
    created_at: str
    read_at: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    tenant_id: int = 1
    tenant_name: str = "EventMonitorAI"


class UserCreate(LoginRequest):
    role: Literal["admin", "operator", "viewer"] = "viewer"


class UserUpdate(BaseModel):
    role: Literal["admin", "operator", "viewer"]
    active: bool = True
    password: str | None = Field(default=None, min_length=10, max_length=256)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    active: bool
    created_at: str
    tenant_id: int = 1
    tenant_name: str = "EventMonitorAI"


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern="^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    admin_username: str = Field(min_length=3, max_length=80)
    admin_password: str = Field(min_length=10, max_length=256)
    plan: str = Field(default="pilot", max_length=40)
    max_devices: int = Field(default=2, ge=1, le=100)
    retention_days: int = Field(default=30, ge=1, le=3650)


class LiveAudioPermissionUpdate(BaseModel):
    device_ids: list[str]


class LiveAudioPermissionRead(BaseModel):
    user_id: int
    username: str
    role: str
    device_ids: list[str]


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=160)
    position_x: float | None = Field(default=None, ge=0, le=100)
    position_y: float | None = Field(default=None, ge=0, le=100)
    enabled: bool = True


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=160)
    position_x: float | None = Field(default=None, ge=0, le=100)
    position_y: float | None = Field(default=None, ge=0, le=100)
    enabled: bool = True


class DeviceRead(DeviceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_seen: str | None


class DeviceTelemetryWrite(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    source_ip: str = ""
    protocol_version: int = Field(default=0, ge=0)
    firmware_version: str = ""
    sample_rate: int = Field(default=0, ge=0)
    uptime_ms: int = Field(default=0, ge=0)
    packets_received: int = Field(default=0, ge=0)
    packets_lost: int = Field(default=0, ge=0)
    peak: int = Field(default=0, ge=0)
    db_level: float = Field(default=0, ge=0)


class DeviceTelemetryRead(DeviceTelemetryWrite):
    model_config = ConfigDict(from_attributes=True)
    loss_rate: float
    last_seen: str


class DeviceLevelPoint(BaseModel):
    device_id: str
    name: str
    timestamp: str
    average_db: float
    maximum_db: float


class SoundMapPoint(BaseModel):
    device_id: str
    name: str
    location: str
    position_x: float | None
    position_y: float | None
    current_db: float | None
    average_db: float | None
    maximum_db: float | None
    exceedances: int


class PushSubscriptionWrite(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)
    p256dh: str = Field(min_length=1, max_length=4096)
    auth: str = Field(min_length=1, max_length=255)


class PushConfigRead(BaseModel):
    enabled: bool
    public_key: str


class WitnessResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: int
    user_id: int
    username: str
    response: Literal["confirmed", "rejected"]
    responded_at: str


class NoiseLogEntry(BaseModel):
    event_id: int
    timestamp: str
    end_timestamp: str | None = None
    duration_seconds: float = 0
    device: str
    label: str
    primary_class_code: str | None
    subclass_code: str | None
    secondary_class_codes: list[str] = Field(default_factory=list)
    secondary_learning_approved_codes: list[str] = Field(default_factory=list)
    primary_learning_approved: bool = True
    classification_status: str
    corrected_by: str | None
    db_level: float
    audio_available: bool = False
    person_id: int | None = None
    person_name: str | None = None
    person_monitoring_excluded: bool = False
    assessment_excluded: bool = False
    assessment_exclusion_reason: str | None = None
    witnesses: list[WitnessResponseRead]


class EventClassWrite(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,80}$")
    name: str = Field(min_length=2, max_length=120)
    level: Literal["base", "fine"]
    parent_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,80}$")
    active: bool = True
    trainable: bool = True
    hidden_by_default: bool = False
    sort_order: int = Field(default=0, ge=0, le=10_000)


class EventClassRead(EventClassWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: str
    updated_at: str


class EventClassUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    level: Literal["base", "fine"]
    parent_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,80}$")
    active: bool = True
    trainable: bool = True
    hidden_by_default: bool = False
    sort_order: int = Field(default=0, ge=0, le=10_000)


class CalibrationCapture(BaseModel):
    level: Literal["low", "medium", "high"]
    reference_db: float = Field(ge=0, le=140)
    device_ids: list[str] = Field(min_length=1)


class DirectCalibrationCapture(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    level: Literal["low", "medium", "high"]
    reference_db: float = Field(ge=0, le=140)


class CalibrationOffsetSet(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    target_offset_db: float = Field(ge=-30, le=30)


class DeviceCalibrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    low_reference_db: float | None
    low_measured_db: float | None
    medium_reference_db: float | None
    medium_measured_db: float | None
    high_reference_db: float | None
    high_measured_db: float | None
    recommended_offset_db: float
    applied_offset_db: float
    reference_points: int
    reference_mae_db: float | None
    updated_at: str


class CalibrationReferenceImport(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str
    device_ids: list[str] = Field(min_length=1)
    tolerance_seconds: float = Field(default=3.0, ge=0.5, le=15.0)


class CalibrationReferenceResultRead(BaseModel):
    device_id: str
    matched_points: int
    mean_reference_db: float
    mean_measured_db: float
    mean_difference_db: float
    mae_db: float
    recommended_offset_db: float


class CalibrationReferenceRunRead(BaseModel):
    id: int
    filename: str
    started_at: str
    ended_at: str
    reference_points: int
    tolerance_seconds: float
    created_by: str
    created_at: str
    results: list[CalibrationReferenceResultRead]


class CalibrationOffsetApply(BaseModel):
    device_ids: list[str] = Field(min_length=1)


class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    category: str = "*"
    min_confidence: float = Field(default=0.7, ge=0, le=1)
    min_db_level: float = 0
    device: str = "*"
    target: Literal["home_assistant"] = "home_assistant"
    cooldown_seconds: int = Field(default=60, ge=0, le=86400)


class RuleRead(RuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_triggered_at: str | None


class AssessmentReferenceRule(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    reference_db: float = Field(ge=0, le=140)


class AssessmentSensitivePeriod(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list)
    include_holidays: bool = False


class AssessmentConfigWrite(BaseModel):
    sensitive_surcharge_db: float = Field(default=6.0, ge=0, le=20)
    apply_to_live: bool = False
    class_rules: dict[str, bool] = Field(default_factory=dict)
    reference_rules: list[AssessmentReferenceRule] = Field(min_length=1)
    sensitive_periods: list[AssessmentSensitivePeriod] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reference_coverage(self) -> "AssessmentConfigWrite":
        coverage = [0] * 1440
        for rule in self.reference_rules:
            start_hour, start_minute = (int(value) for value in rule.start_time.split(":"))
            end_hour, end_minute = (int(value) for value in rule.end_time.split(":"))
            start = start_hour * 60 + start_minute
            end = end_hour * 60 + end_minute
            minutes = range(1440) if start == end else (
                range(start, end) if start < end else [*range(start, 1440), *range(end)]
            )
            for minute in minutes:
                coverage[minute] += 1
        if any(value != 1 for value in coverage):
            raise ValueError("Grenzwert-Zeitregeln müssen den ganzen Tag lückenlos und ohne Überschneidung abdecken")
        return self


class AssessmentConfigRead(AssessmentConfigWrite):
    updated_at: str


class PersonWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    active: bool = True
    monitoring_enabled: bool = True


class PersonUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    active: bool = True
    monitoring_enabled: bool = True


class PersonRead(PersonWrite):
    id: int
    created_at: str
    updated_at: str
    frequency: int = 0
    total_duration_seconds: float = 0
    categories: dict[str, int] = Field(default_factory=dict)
    photo_available: bool = False
    video_available: bool = False
    video_audio_available: bool = False
    video_voice_similarity: float | None = None
    video_voice_cluster_id: int | None = None
    video_voice_cluster_name: str | None = None


class PersonAssignmentWrite(BaseModel):
    person_id: int | None = None


class SpeakerAnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    model_name: str
    total: int
    processed: int
    clustered: int
    skipped: int
    requested_by: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    message: str


class SpeakerClusterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    person_id: int | None = None


class SpeakerSampleReview(BaseModel):
    action: Literal["confirm", "reject", "no_voice", "move", "new_cluster"]
    target_cluster_id: int | None = None


class PersonMediaUpload(BaseModel):
    media_type: Literal["photo", "video"]
    filename: str = Field(min_length=1, max_length=180)
    mime_type: str = Field(min_length=1, max_length=100)
    content_base64: str
