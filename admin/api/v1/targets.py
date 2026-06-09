"""Dynamic and live target CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from nonebot_plugin_orm import get_session

from admin.deps import AdminUser, RequireSetup
from admin.schemas.targets import (
    DynamicTargetCreate,
    DynamicTargetResponse,
    DynamicTargetUpdate,
    LiveTargetCreate,
    LiveTargetResponse,
    LiveTargetUpdate,
)
from admin.services.monitor_bridge import reload_all_monitors
from admin.services.target_metadata import (
    resolve_dynamic_target_name,
    resolve_live_streamer_name,
    resolve_live_target_name,
    resolve_up_name,
)
from shared.audit.service import write_audit, write_system_event
from shared.config.service import get_config_service
from shared.db.enums import AuditAction, SystemEventType
from shared.db.models import (
    DynamicTarget,
    DynamicTargetGroup,
    DynamicTargetUser,
    LiveTarget,
    LiveTargetGroup,
    LiveTargetUser,
)

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
        at_all=target.at_all,
        group_ids=[g.group_id for g in target.groups],
        user_ids=[u.user_id for u in target.users],
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _live_to_response(target: LiveTarget) -> LiveTargetResponse:
    return LiveTargetResponse(
        id=target.id,
        room_id=target.room_id,
        name=target.name,
        enabled=target.enabled,
        at_all=target.at_all,
        group_ids=[g.group_id for g in target.groups],
        user_ids=[u.user_id for u in target.users],
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _normalize_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _ensure_recipients(group_ids: list[str], user_ids: list[str]) -> None:
    if not group_ids and not user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择一个群组或好友",
        )


def _normalize_group_ids(group_ids: list[str]) -> list[str]:
    return _normalize_ids(group_ids)


def _normalize_user_ids(user_ids: list[str]) -> list[str]:
    return _normalize_ids(user_ids)


async def _sync_groups_dynamic(session, target: DynamicTarget, group_ids: list[str]) -> None:
    normalized = _normalize_group_ids(group_ids)
    for group in list(target.groups):
        await session.delete(group)
    await session.flush()
    target.groups = [DynamicTargetGroup(group_id=gid) for gid in normalized]


async def _sync_users_dynamic(session, target: DynamicTarget, user_ids: list[str]) -> None:
    normalized = _normalize_user_ids(user_ids)
    for user in list(target.users):
        await session.delete(user)
    await session.flush()
    target.users = [DynamicTargetUser(user_id=uid) for uid in normalized]


async def _sync_groups_live(session, target: LiveTarget, group_ids: list[str]) -> None:
    normalized = _normalize_group_ids(group_ids)
    for group in list(target.groups):
        await session.delete(group)
    await session.flush()
    target.groups = [LiveTargetGroup(group_id=gid) for gid in normalized]


async def _sync_users_live(session, target: LiveTarget, user_ids: list[str]) -> None:
    normalized = _normalize_user_ids(user_ids)
    for user in list(target.users):
        await session.delete(user)
    await session.flush()
    target.users = [LiveTargetUser(user_id=uid) for uid in normalized]


async def _refresh_missing_dynamic_names(targets: list[DynamicTarget]) -> None:
    for target in targets:
        if target.name:
            continue
        name = await resolve_up_name(target.uid)
        if name:
            target.name = name


async def _refresh_missing_live_names(targets: list[LiveTarget]) -> None:
    for target in targets:
        if target.name:
            continue
        name = await resolve_live_streamer_name(target.room_id)
        if name:
            target.name = name


# --- Dynamic targets ---

@router.get("/dynamic-targets", response_model=list[DynamicTargetResponse])
async def list_dynamic_targets(_: AdminUser):
    session = get_session()
    async with session.begin():
        stmt = select(DynamicTarget).options(
            selectinload(DynamicTarget.groups),
            selectinload(DynamicTarget.users),
        )
        targets = (await session.scalars(stmt)).all()
        await _refresh_missing_dynamic_names(targets)
        return [_dynamic_to_response(t) for t in targets]


@router.post("/dynamic-targets", response_model=DynamicTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_dynamic_target(request: Request, body: DynamicTargetCreate, user: AdminUser):
    session = get_session()
    async with session.begin():
        existing = await session.scalar(select(DynamicTarget).where(DynamicTarget.uid == body.uid))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="UID already exists")

        resolved_name = await resolve_dynamic_target_name(body.uid, body.name)
        if not resolved_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取 UP 主信息，请检查 UID 是否正确，或手动填写显示名称",
            )
        _ensure_recipients(body.group_ids, body.user_ids)
        target = DynamicTarget(uid=body.uid, name=resolved_name, enabled=body.enabled, at_all=body.at_all)
        await _sync_groups_dynamic(session, target, body.group_ids)
        await _sync_users_dynamic(session, target, body.user_ids)
        session.add(target)
        await session.flush()
        await session.refresh(target, ["groups", "users"])
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
async def get_dynamic_target(target_id: int, _: AdminUser):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(DynamicTarget)
            .where(DynamicTarget.id == target_id)
            .options(
                selectinload(DynamicTarget.groups),
                selectinload(DynamicTarget.users),
            )
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        response = _dynamic_to_response(target)
    return response


@router.patch("/dynamic-targets/{target_id}", response_model=DynamicTargetResponse)
async def update_dynamic_target(
    target_id: int, request: Request, body: DynamicTargetUpdate, user: AdminUser
):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(DynamicTarget)
            .where(DynamicTarget.id == target_id)
            .options(
                selectinload(DynamicTarget.groups),
                selectinload(DynamicTarget.users),
            )
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        if body.uid is not None:
            new_uid = body.uid.strip()
            if not new_uid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="UID 不能为空",
                )
            if new_uid != target.uid:
                existing = await session.scalar(
                    select(DynamicTarget).where(DynamicTarget.uid == new_uid)
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="UID already exists",
                    )
                target.uid = new_uid

        if body.name is not None:
            stripped = body.name.strip()
            target.name = stripped if stripped else None
        if body.enabled is not None:
            target.enabled = body.enabled
        if body.at_all is not None:
            target.at_all = body.at_all
        if body.group_ids is not None:
            await _sync_groups_dynamic(session, target, body.group_ids)
        if body.user_ids is not None:
            await _sync_users_dynamic(session, target, body.user_ids)
        if body.group_ids is not None or body.user_ids is not None:
            _ensure_recipients(
                [g.group_id for g in target.groups],
                [u.user_id for u in target.users],
            )
        if not target.name:
            resolved = await resolve_up_name(target.uid)
            if not resolved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法获取 UP 主信息，请检查 UID 是否正确，或手动填写显示名称",
                )
            target.name = resolved
        await session.flush()
        await session.refresh(target, ["groups", "users"])
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
async def delete_dynamic_target(target_id: int, request: Request, user: AdminUser):
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
async def list_live_targets(_: AdminUser):
    session = get_session()
    async with session.begin():
        stmt = select(LiveTarget).options(
            selectinload(LiveTarget.groups),
            selectinload(LiveTarget.users),
        )
        targets = (await session.scalars(stmt)).all()
        await _refresh_missing_live_names(targets)
        return [_live_to_response(t) for t in targets]


@router.post("/live-targets", response_model=LiveTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_live_target(request: Request, body: LiveTargetCreate, user: AdminUser):
    session = get_session()
    async with session.begin():
        existing = await session.scalar(select(LiveTarget).where(LiveTarget.room_id == body.room_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Room already exists")

        resolved_name = await resolve_live_target_name(body.room_id, body.name)
        if not resolved_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取直播间信息，请检查房间号是否正确，或手动填写显示名称",
            )
        _ensure_recipients(body.group_ids, body.user_ids)
        target = LiveTarget(room_id=body.room_id, name=resolved_name, enabled=body.enabled, at_all=body.at_all)
        await _sync_groups_live(session, target, body.group_ids)
        await _sync_users_live(session, target, body.user_ids)
        session.add(target)
        await session.flush()
        await session.refresh(target, ["groups", "users"])
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
async def get_live_target(target_id: int, _: AdminUser):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(LiveTarget)
            .where(LiveTarget.id == target_id)
            .options(
                selectinload(LiveTarget.groups),
                selectinload(LiveTarget.users),
            )
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        response = _live_to_response(target)
    return response


@router.patch("/live-targets/{target_id}", response_model=LiveTargetResponse)
async def update_live_target(
    target_id: int, request: Request, body: LiveTargetUpdate, user: AdminUser
):
    session = get_session()
    async with session.begin():
        target = await session.scalar(
            select(LiveTarget)
            .where(LiveTarget.id == target_id)
            .options(
                selectinload(LiveTarget.groups),
                selectinload(LiveTarget.users),
            )
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        if body.room_id is not None:
            new_room_id = body.room_id.strip()
            if not new_room_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="房间号不能为空",
                )
            if new_room_id != target.room_id:
                existing = await session.scalar(
                    select(LiveTarget).where(LiveTarget.room_id == new_room_id)
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Room already exists",
                    )
                target.room_id = new_room_id

        if body.name is not None:
            stripped = body.name.strip()
            target.name = stripped if stripped else None
        if body.enabled is not None:
            target.enabled = body.enabled
        if body.at_all is not None:
            target.at_all = body.at_all
        if body.group_ids is not None:
            await _sync_groups_live(session, target, body.group_ids)
        if body.user_ids is not None:
            await _sync_users_live(session, target, body.user_ids)
        if body.group_ids is not None or body.user_ids is not None:
            _ensure_recipients(
                [g.group_id for g in target.groups],
                [u.user_id for u in target.users],
            )
        if not target.name:
            resolved = await resolve_live_streamer_name(target.room_id)
            if not resolved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法获取直播间信息，请检查房间号是否正确，或手动填写显示名称",
                )
            target.name = resolved
        await session.flush()
        await session.refresh(target, ["groups", "users"])
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
async def delete_live_target(target_id: int, request: Request, user: AdminUser):
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
