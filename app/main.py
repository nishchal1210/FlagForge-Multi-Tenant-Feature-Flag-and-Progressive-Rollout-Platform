
from fastapi import FastAPI

from app.api.router import api_router

from app.api.routes.sdk_config import router as sdk_router



app = FastAPI(
    title="FlagForge Control Plane",
    version="0.1.0",
    description=(
        "Multi-tenant feature flag and "
        "progressive rollout platform"
    ),
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