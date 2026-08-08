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
