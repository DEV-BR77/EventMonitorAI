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
