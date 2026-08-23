
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagCreate(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
    )
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    default_value: bool = False


class FeatureFlagUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    enabled: bool | None = None
    default_value: bool | None = None


class FeatureFlagResponse(BaseModel):
    id: uuid.UUID
    environment_id: uuid.UUID
    key: str
    name: str
    enabled: bool
    default_value: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)