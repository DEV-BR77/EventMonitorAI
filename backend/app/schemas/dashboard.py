from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserCreate(LoginRequest):
    role: Literal["admin", "operator", "viewer"] = "viewer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    active: bool
    created_at: str


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    location: str = ""
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


class CalibrationCapture(BaseModel):
    level: Literal["low", "medium", "high"]
    reference_db: float = Field(ge=0, le=140)
    device_ids: list[str] = Field(min_length=1)


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
    updated_at: str


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
