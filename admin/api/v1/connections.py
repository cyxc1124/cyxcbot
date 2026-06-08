"""External connection status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.connections import ConnectionsStatusResponse
from admin.services.connection_status import get_connections_status

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
    dependencies=[RequireSetup],
)


@router.get("/status", response_model=ConnectionsStatusResponse)
async def connections_status(_: CurrentUser):
    return ConnectionsStatusResponse(**await get_connections_status())
