import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SDKKeyCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )


class SDKKeyCreatedResponse(BaseModel):
    id: uuid.UUID
    environment_id: uuid.UUID
    name: str
    key: str
    created_at: datetime


class SDKKeyResponse(BaseModel):
    id: uuid.UUID
    environment_id: uuid.UUID
    name: str
    created_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)