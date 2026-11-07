import asyncio
import json
import logging

from redis.exceptions import RedisError

from app.core.redis import async_redis
from app.realtime.connection_manager import (
    sse_manager,
)
from app.services.config_events import (
    CONFIG_UPDATE_CHANNEL,
)


logger = logging.getLogger(__name__)


async def listen_for_config_updates() -> None:
    while True:
        try:
            async with async_redis.pubsub() as pubsub:
                await pubsub.subscribe(
                    CONFIG_UPDATE_CHANNEL
                )

                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue

                    event = json.loads(
                        message["data"]
                    )

                    environment_id = event.get(
                        "environment_id"
                    )

                    if environment_id is None:
                        continue

                    await sse_manager.broadcast(
                        environment_id=environment_id,
                        event=event,
                    )

        except asyncio.CancelledError:
            raise

        except (
            RedisError,
            json.JSONDecodeError,
        ):
            logger.exception(
                "Redis subscriber failed; reconnecting"
            )

            await asyncio.sleep(2)