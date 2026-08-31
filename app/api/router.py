from fastapi import APIRouter

from app.api.routes import (
    config_versions,
    environments,
    flags,
    projects,
    rules,
    sdk_keys,
    tenants,
)


api_router = APIRouter()

api_router.include_router(tenants.router)
api_router.include_router(projects.router)
api_router.include_router(environments.router)
api_router.include_router(sdk_keys.router)
api_router.include_router(flags.router)
api_router.include_router(rules.router)
api_router.include_router(config_versions.router)
