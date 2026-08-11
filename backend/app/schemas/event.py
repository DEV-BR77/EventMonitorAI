from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    timestamp: str
    end_timestamp: str | None = None
    duration_seconds: float = Field(default=0.975, ge=0.0)

    event_type: str = "AUDIO"
    label: str
    confidence: float = Field(ge=0.0, le=1.0)

    db_level: float
    avg_db_level: float | None = None

    device: str


class EventRead(EventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label_de: str
    category: str
    primary_class_code: str | None
    subclass_code: str | None
    secondary_class_codes: list[str] = Field(default_factory=list)
    secondary_learning_approved_codes: list[str] = Field(default_factory=list)
    primary_learning_approved: bool = True
    classification_status: str
    corrected_by: str | None
    corrected_at: str | None
    audio_available: bool = False
    display_suppressed: bool = False
    person_id: int | None = None
    person_monitoring_excluded: bool = False
    assessment_excluded: bool = False
    assessment_exclusion_reason: str | None = None


class EventClassificationUpdate(BaseModel):
    primary_class_code: str = Field(pattern=r"^[A-Z0-9_]{2,80}$")
    subclass_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,80}$")
    secondary_class_codes: list[str] = Field(default_factory=list, max_length=12)
    secondary_learning_approved_codes: list[str] = Field(default_factory=list, max_length=12)
    primary_learning_approved: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class EventClassificationRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    primary_class_code: str
    subclass_code: str | None
    secondary_class_codes: list[str] = Field(default_factory=list)
    learning_approved_codes: list[str] = Field(default_factory=list)
    status: str
    actor: str
    reason: str
    created_at: str


class TrainingExampleRead(BaseModel):
    event_id: int
    device_id: str
    timestamp: str
    primary_class_code: str
    subclass_code: str
    assignment_role: str = "primary"
    label: str
    confidence: float
    clip_sha256: str
    audio_url: str


class ReviewQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: str
    label: str
    label_de: str
    confidence: float
    db_level: float
    device: str
    primary_class_code: str | None
    subclass_code: str | None
    secondary_class_codes: list[str] = Field(default_factory=list)
    secondary_learning_approved_codes: list[str] = Field(default_factory=list)
    primary_learning_approved: bool = True
    classification_status: str
    audio_available: bool = False
    person_id: int | None = None
    assessment_excluded: bool = False
    assessment_exclusion_reason: str | None = None


class ReviewSummary(BaseModel):
    open_unknown: int
    open_recognized: int
    completed_unknown: int
    completed_recognized: int
    excluded_context_only: int
    by_class: dict[str, dict[str, int]]


class BulkClassificationUpdate(EventClassificationUpdate):
    event_ids: list[int] = Field(min_length=1, max_length=500)
    assessment_excluded: bool = False
    assessment_exclusion_reason: str | None = Field(default=None, max_length=80)


class AssessmentExclusionUpdate(BaseModel):
    excluded: bool
    reason: str | None = Field(default=None, max_length=80)


class ReviewRunCreate(BaseModel):
    kind: str = Field(default="manual", pattern=r"^(manual|automatic|nightly)$")


class ReviewRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    status: str
    cursor_event_id: int
    processed: int
    changed: int
    total: int
    requested_by: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    message: str


class HistoricalImportFile(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    content_base64: str


class HistoricalImportRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    files: list[HistoricalImportFile] = Field(min_length=1, max_length=20)


class HistoricalImportResult(BaseModel):
    imported_events: int
    imported_audio: int
    skipped: int
    messages: list[str]
