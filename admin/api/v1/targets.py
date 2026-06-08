"""Dynamic and live target CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from nonebot_plugin_orm import get_session

from admin.deps import CurrentUser, RequireSetup
from admin.schemas.targets import (
    DynamicTargetCreate,
    DynamicTargetResponse,
    DynamicTargetUpdate,
    LiveTargetCreate,
    LiveTargetResponse,
    LiveTargetUpdate,
)
from admin.services.monitor_bridge import reload_all_monitors
from shared.audit.service import write_audit, write_system_event
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType
from shared.db.models import DynamicTarget, DynamicTargetGroup, LiveTarget, LiveTargetGroup

router = APIRouter(
    tags=["targets"],
    dependencies=[RequireSetup],
)


def _dynamic_to_response(target: DynamicTarget) -> DynamicTargetResponse:
    return DynamicTargetResponse(
        id=target.id,
        uid=target.uid,
        name=target.name,
        enabled=target.enabled,
        group_ids=[g.group_id for g in target.groups],
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _live_to_response(target: LiveTarget) -> LiveTargetResponse:
    return LiveTargetResponse(
        id=target.id,
        room_id=target.room_id,
        name=target.name,
        enabled=target.enabled,
        group_ids=[g.group_id for g in target.groups],
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


async def _sync_groups_dynamic(session, target: DynamicTarget, group_ids: list[str]) -> None:
    target.groups.clear()
    for gid in group_ids:
        target.groups.append(DynamicTargetGroup(group_id=str(gid)))


async def _sync_groups_live(session, target: LiveTarget, group_ids: list[str]) -> None:
    target.groups.clear()
    for gid in group_ids:
        target.groups.append(LiveTargetGroup(group_id=str(gid)))


# --- Dynamic targets ---

@router.get("/dynamic-targets", response_model=list[DynamicTargetResponse])
async def list_dynamic_targets(_: CurrentUser):
    session = get_session()
    async with session.begin():
        stmt = select(DynamicTarget).options(selectinload(DynamicTarget.groups))
        targets = (await session.scalars(stmt)).all()
    return [_dynamic_to_response(t) for t in targets]


@router.post("/dynamic-targets", response_model=DynamicTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_dynamic_target(request: Request, body: DynamicTargetCreate, user: CurrentUser):
    session = get_session()
    async with session.begin():
        existing = await session.scalar(select(DynamicTarget).where(DynamicTarget.uid == body.uid))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="UID already exists")

        target = DynamicTarget(uid=body.uid, name=body.name, enabled=body.enabled)
        await _sync_groups_dynamic(session, target, body.group_ids)
        session.add(target)
        await session.flush()
        await session.refresh(target, ["groups"])
        response = _dynamic_to_response(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.DYNAMIC_TARGET_CREATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"uid": body.uid}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, f"Dynamic target {body.uid} created")
    return response


@router.get("/dynamic-targets/{target_id}", response_model=DynamicTargetResponse)
async def get_dynamic_target(target_id: int, _: CurrentUser):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(DynamicTarget)
            .where(DynamicTarget.id == target_id)
            .options(selectinload(DynamicTarget.groups))
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        response = _dynamic_to_response(target)
    return response


@router.patch("/dynamic-targets/{target_id}", response_model=DynamicTargetResponse)
async def update_dynamic_target(
    target_id: int, request: Request, body: DynamicTargetUpdate, user: CurrentUser
):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(DynamicTarget)
            .where(DynamicTarget.id == target_id)
            .options(selectinload(DynamicTarget.groups))
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        if body.name is not None:
            target.name = body.name
        if body.enabled is not None:
            target.enabled = body.enabled
        if body.group_ids is not None:
            await _sync_groups_dynamic(session, target, body.group_ids)
        await session.flush()
        await session.refresh(target, ["groups"])
        response = _dynamic_to_response(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.DYNAMIC_TARGET_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"id": target_id, "uid": response.uid}),
    )
    return response


@router.delete("/dynamic-targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dynamic_target(target_id: int, request: Request, user: CurrentUser):
    session = get_session()
    async with session.begin():
        target = await session.get(DynamicTarget, target_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        uid = target.uid
        await session.delete(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.DYNAMIC_TARGET_DELETE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"uid": uid}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, f"Dynamic target {uid} deleted")


# --- Live targets ---

@router.get("/live-targets", response_model=list[LiveTargetResponse])
async def list_live_targets(_: CurrentUser):
    session = get_session()
    async with session.begin():
        stmt = select(LiveTarget).options(selectinload(LiveTarget.groups))
        targets = (await session.scalars(stmt)).all()
    return [_live_to_response(t) for t in targets]


@router.post("/live-targets", response_model=LiveTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_live_target(request: Request, body: LiveTargetCreate, user: CurrentUser):
    session = get_session()
    async with session.begin():
        existing = await session.scalar(select(LiveTarget).where(LiveTarget.room_id == body.room_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room already exists")

        target = LiveTarget(room_id=body.room_id, name=body.name, enabled=body.enabled)
        await _sync_groups_live(session, target, body.group_ids)
        session.add(target)
        await session.flush()
        await session.refresh(target, ["groups"])
        response = _live_to_response(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.LIVE_TARGET_CREATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"room_id": body.room_id}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, f"Live target {body.room_id} created")
    return response


@router.get("/live-targets/{target_id}", response_model=LiveTargetResponse)
async def get_live_target(target_id: int, _: CurrentUser):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(LiveTarget)
            .where(LiveTarget.id == target_id)
            .options(selectinload(LiveTarget.groups))
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        response = _live_to_response(target)
    return response


@router.patch("/live-targets/{target_id}", response_model=LiveTargetResponse)
async def update_live_target(
    target_id: int, request: Request, body: LiveTargetUpdate, user: CurrentUser
):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(LiveTarget)
            .where(LiveTarget.id == target_id)
            .options(selectinload(LiveTarget.groups))
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        if body.name is not None:
            target.name = body.name
        if body.enabled is not None:
            target.enabled = body.enabled
        if body.group_ids is not None:
            await _sync_groups_live(session, target, body.group_ids)
        await session.flush()
        await session.refresh(target, ["groups"])
        response = _live_to_response(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.LIVE_TARGET_UPDATE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"id": target_id, "room_id": response.room_id}),
    )
    return response


@router.delete("/live-targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_live_target(target_id: int, request: Request, user: CurrentUser):
    session = get_session()
    async with session.begin():
        target = await session.get(LiveTarget, target_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        room_id = target.room_id
        await session.delete(target)

    await get_config_service().reload()
    await reload_all_monitors()

    ip = request.client.host if request.client else None
    await write_audit(
        AuditAction.LIVE_TARGET_DELETE,
        actor_user_id=user.id,
        actor_username=user.username,
        ip_address=ip,
        details=get_config_service().serialize_details({"room_id": room_id}),
    )
    await write_system_event(SystemEventType.CONFIG_RELOAD, f"Live target {room_id} deleted")
