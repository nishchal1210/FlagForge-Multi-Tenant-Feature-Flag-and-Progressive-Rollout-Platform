
from fastapi import FastAPI

from app.api.router import api_router

from app.api.routes.sdk_config import router as sdk_router

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.router import api_router
from app.api.routes.sdk_config import (
    router as sdk_router,
)
from app.core.redis import async_redis
from app.realtime.redis_subscriber import (
    listen_for_config_updates,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber_task = asyncio.create_task(
        listen_for_config_updates()
    )

    yield

    subscriber_task.cancel()

    with suppress(asyncio.CancelledError):
        await subscriber_task

    await async_redis.aclose()



app = FastAPI(
    title="FlagForge Control Plane",
    version="0.1.0",
    description=(
        "Multi-tenant feature flag and "
        "progressive rollout platform"
    ),
    lifespan = lifespan,
)

app.include_router(
    api_router,
    prefix="/api/v1",
)

app.include_router(
    sdk_router,
    prefix="/api/sdk/v1",
)

# This attaches all routes collected by api_router to the application.
# The prefix /api/v1 is automatically placed before every route.


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}