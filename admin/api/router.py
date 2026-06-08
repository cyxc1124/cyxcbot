"""Main API router."""

from fastapi import APIRouter

from admin.api.v1 import audit, auth, groups, monitors, settings, setup, targets

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(settings.router)
api_router.include_router(targets.router)
api_router.include_router(monitors.router)
api_router.include_router(groups.router)
api_router.include_router(audit.router)
