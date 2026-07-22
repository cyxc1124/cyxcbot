"""Rust player points / Steam binding admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from admin.deps import AdminUser, RequireSetup
from admin.schemas.rust_player import (
    RustCheckInConfigResponse,
    RustCheckInConfigUpdateRequest,
    RustPlayerOverviewItem,
    RustPlayerOverviewResponse,
    RustPlayerPointsUpdateRequest,
    RustPlayerPointsUpdateResponse,
)
from shared.config.rust_player import (
    normalize_checkin_online_bonus,
    normalize_checkin_points_range,
    normalize_checkin_rcon_binding_id,
    resolve_checkin_rcon_binding,
)
from shared.config.service import get_config_service
from shared.rust_player import store

router = APIRouter(
    prefix="/rust-players",
    tags=["rust-players"],
    dependencies=[RequireSetup],
)


@router.get("/overview", response_model=RustPlayerOverviewResponse)
async def list_rust_player_overview(_: AdminUser) -> RustPlayerOverviewResponse:
    items = await store.list_player_overview()
    return RustPlayerOverviewResponse(
        items=[RustPlayerOverviewItem(**item) for item in items]
    )


@router.patch("/points", response_model=RustPlayerPointsUpdateResponse)
async def update_rust_player_points(
    body: RustPlayerPointsUpdateRequest,
    _: AdminUser,
) -> RustPlayerPointsUpdateResponse:
    try:
        points = await store.set_group_points(body.group_id, body.user_id, body.points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RustPlayerPointsUpdateResponse(
        group_id=str(body.group_id).strip(),
        user_id=str(body.user_id).strip(),
        points=points,
    )


@router.delete("/steam-bindings/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rust_steam_binding(user_id: str, _: AdminUser) -> None:
    deleted = await store.delete_steam_binding(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到 SteamID 绑定")


@router.get("/checkin-config", response_model=RustCheckInConfigResponse)
async def get_rust_checkin_config(_: AdminUser) -> RustCheckInConfigResponse:
    snap = get_config_service().get_snapshot()
    return RustCheckInConfigResponse(
        min_points=snap.rust_checkin_points_min,
        max_points=snap.rust_checkin_points_max,
        online_bonus_points=snap.rust_checkin_online_bonus_points,
        rcon_binding_id=snap.rust_checkin_rcon_binding_id,
    )


@router.patch("/checkin-config", response_model=RustCheckInConfigResponse)
async def update_rust_checkin_config(
    body: RustCheckInConfigUpdateRequest,
    _: AdminUser,
) -> RustCheckInConfigResponse:
    try:
        min_points, max_points = normalize_checkin_points_range(
            body.min_points, body.max_points
        )
        online_bonus_points = normalize_checkin_online_bonus(body.online_bonus_points)
        rcon_binding_id = normalize_checkin_rcon_binding_id(body.rcon_binding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    snap = get_config_service().get_snapshot()
    if (
        rcon_binding_id
        and resolve_checkin_rcon_binding(snap.rust_rcon_bindings, rcon_binding_id)
        is None
    ):
        raise HTTPException(status_code=400, detail="指定的 RCON 绑定不存在或未启用")

    svc = get_config_service()
    await svc.set_settings(
        {
            "rust_checkin_points_min": str(min_points),
            "rust_checkin_points_max": str(max_points),
            "rust_checkin_online_bonus_points": str(online_bonus_points),
            "rust_checkin_rcon_binding_id": str(rcon_binding_id),
        }
    )
    await svc.reload()
    return RustCheckInConfigResponse(
        min_points=min_points,
        max_points=max_points,
        online_bonus_points=online_bonus_points,
        rcon_binding_id=rcon_binding_id,
    )
