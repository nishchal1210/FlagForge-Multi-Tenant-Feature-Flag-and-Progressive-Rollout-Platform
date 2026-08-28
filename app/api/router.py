
from fastapi import APIRouter

from app.api.routes import environments, flags, projects, rules, tenants


api_router = APIRouter()

api_router.include_router(tenants.router)
api_router.include_router(projects.router)
api_router.include_router(environments.router)
api_router.include_router(flags.router)
api_router.include_router(rules.router)
