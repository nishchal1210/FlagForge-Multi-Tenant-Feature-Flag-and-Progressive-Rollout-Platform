import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConfigVersionMetadata(BaseModel):
    id: uuid.UUID
    environment_id: uuid.UUID
    version: int
    checksum: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfigVersionResponse(ConfigVersionMetadata):
    configuration: dict[str, Any]



class SDKConfigurationResponse(BaseModel):
    version: int
    checksum: str
    configuration: dict[str, Any]