"""Main API router."""

from fastapi import APIRouter

from admin.api.v1 import (
    about,
    auth,
    bilibili,
    connections,
    groups,
    link_parser,
    logs,
    monitors,
    private,
    rust_rcon,
    rust_rcon_policies,
    settings,
    setup,
    targets,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(about.router)
api_router.include_router(settings.router)
api_router.include_router(bilibili.router)
api_router.include_router(targets.router)
api_router.include_router(monitors.router)
api_router.include_router(connections.router)
api_router.include_router(groups.router)
api_router.include_router(private.router)
api_router.include_router(link_parser.router)
api_router.include_router(rust_rcon.router)
api_router.include_router(rust_rcon_policies.router)
api_router.include_router(logs.router)
