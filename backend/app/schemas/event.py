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
    classification_status: str
    corrected_by: str | None
    corrected_at: str | None


class EventClassificationUpdate(BaseModel):
    primary_class_code: str = Field(pattern=r"^[A-Z0-9_]{2,80}$")
    subclass_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,80}$")
    reason: str = Field(min_length=3, max_length=500)


class EventClassificationRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    primary_class_code: str
    subclass_code: str | None
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
    label: str
    confidence: float
    clip_sha256: str
    audio_url: str
