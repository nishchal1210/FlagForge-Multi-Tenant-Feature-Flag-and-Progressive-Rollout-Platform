
from fastapi import FastAPI

from app.api.router import api_router


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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}