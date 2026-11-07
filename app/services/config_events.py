import json
import uuid

from app.core.redis import sync_redis


CONFIG_UPDATE_CHANNEL = "flagforge:config-updates"


def publish_config_update(
    environment_id: uuid.UUID,
    version: int,
    checksum: str,
) -> None:
    event = {
        "type": "config_updated",
        "environment_id": str(environment_id),
        "version": version,
        "checksum": checksum,
    }

    sync_redis.publish(
        CONFIG_UPDATE_CHANNEL,
        json.dumps(event),
    )