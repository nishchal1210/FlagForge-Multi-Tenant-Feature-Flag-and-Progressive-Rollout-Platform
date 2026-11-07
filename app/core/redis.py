from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings


sync_redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)

async_redis = AsyncRedis.from_url(
    settings.redis_url,
    decode_responses=True,
)