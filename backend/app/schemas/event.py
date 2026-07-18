from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    timestamp: str
    event_type: str = "AUDIO"
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    db_level: float
    device: str


class EventRead(EventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label_de: str
    category: str