
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
    )


class EnvironmentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)