"""External connection status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from admin.deps import AdminUser, RequireSetup
from admin.schemas.connections import (
    BotConnectionsStatusResponse,
    ConnectionsStatusResponse,
)
from admin.services.connection_status import (
    get_connections_status,
    get_official_qq_connection_status,
    get_qq_connection_status,
)

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
    dependencies=[RequireSetup],
)


@router.get("/status", response_model=ConnectionsStatusResponse)
async def connections_status(_: AdminUser):
    return ConnectionsStatusResponse(**await get_connections_status())


@router.get("/bots", response_model=BotConnectionsStatusResponse)
async def bot_connections_status(_: AdminUser):
    return BotConnectionsStatusResponse(
        qq=await get_qq_connection_status(),
        official_qq=await get_official_qq_connection_status(),
    )
