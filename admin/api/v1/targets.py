"""Dynamic, live and X target CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from admin.deps import AdminUser, RequireSetup
from admin.schemas.targets import (
    DynamicTargetCreate,
    DynamicTargetResponse,
    DynamicTargetUpdate,
    LiveTargetCreate,
    LiveTargetResponse,
    LiveTargetUpdate,
    XTargetCreate,
    XTargetResponse,
    XTargetUpdate,
)
from admin.services.target_metadata import (
    resolve_dynamic_target_name,
    resolve_live_streamer_name,
    resolve_live_target_name,
    resolve_missing_dynamic_target_names,
    resolve_missing_live_target_names,
    resolve_missing_x_target_names,
    resolve_up_name,
    resolve_x_target_name,
    resolve_x_user,
)
from shared.config.service import get_config_service
from shared.db.models import (
    DynamicTarget,
    DynamicTargetGroup,
    DynamicTargetUser,
    LiveTarget,
    LiveTargetGroup,
    LiveTargetUser,
    XTarget,
    XTargetGroup,
    XTargetUser,
)
from shared.monitor.background_task import spawn_background_task

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


def _x_to_response(target: XTarget) -> XTargetResponse:
    return XTargetResponse(
        id=target.id,
        username=target.username,
        name=target.name,
        enabled=target.enabled,
        at_all=target.at_all,
        group_ids=[g.group_id for g in target.groups],
        user_ids=[u.user_id for u in target.users],
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _normalize_x_username(username: str) -> str:
    return (username or "").lstrip("@").strip()


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


async def _sync_groups_dynamic(
    session, target: DynamicTarget, group_ids: list[str]
) -> None:
    normalized = _normalize_group_ids(group_ids)
    for group in list(target.groups):
        await session.delete(group)
    await session.flush()
    target.groups = [DynamicTargetGroup(group_id=gid) for gid in normalized]


async def _sync_users_dynamic(
    session, target: DynamicTarget, user_ids: list[str]
) -> None:
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


async def _sync_groups_x(session, target: XTarget, group_ids: list[str]) -> None:
    normalized = _normalize_group_ids(group_ids)
    for group in list(target.groups):
        await session.delete(group)
    await session.flush()
    target.groups = [XTargetGroup(group_id=gid) for gid in normalized]


async def _sync_users_x(session, target: XTarget, user_ids: list[str]) -> None:
    normalized = _normalize_user_ids(user_ids)
    for user in list(target.users):
        await session.delete(user)
    await session.flush()
    target.users = [XTargetUser(user_id=uid) for uid in normalized]


# --- Dynamic targets ---


@router.get("/dynamic-targets", response_model=list[DynamicTargetResponse])
async def list_dynamic_targets(_: AdminUser):
    async with get_session() as session:
        async with session.begin():
            stmt = select(DynamicTarget).options(
                selectinload(DynamicTarget.groups),
                selectinload(DynamicTarget.users),
            )
            targets = (await session.scalars(stmt)).all()
            response = [_dynamic_to_response(t) for t in targets]
            missing = [(t.id, t.uid) for t in targets if not t.name]

    if missing:
        spawn_background_task(
            "补全动态 target 名称",
            resolve_missing_dynamic_target_names(missing),
        )
    return response


@router.post(
    "/dynamic-targets",
    response_model=DynamicTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dynamic_target(body: DynamicTargetCreate, _: AdminUser):
    _ensure_recipients(body.group_ids, body.user_ids)

    async with get_session() as session:
        async with session.begin():
            existing = await session.scalar(
                select(DynamicTarget).where(DynamicTarget.uid == body.uid)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="UID already exists"
                )

        resolved_name = await resolve_dynamic_target_name(body.uid, body.name)
        if not resolved_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取 UP 主信息，请检查 UID 是否正确，或手动填写显示名称",
            )

        async with session.begin():
            existing = await session.scalar(
                select(DynamicTarget).where(DynamicTarget.uid == body.uid)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="UID already exists"
                )

            target = DynamicTarget(
                uid=body.uid,
                name=resolved_name,
                enabled=body.enabled,
                at_all=body.at_all,
            )
            await _sync_groups_dynamic(session, target, body.group_ids)
            await _sync_users_dynamic(session, target, body.user_ids)
            session.add(target)
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _dynamic_to_response(target)

    await get_config_service().reload()

    return response


@router.get("/dynamic-targets/{target_id}", response_model=DynamicTargetResponse)
async def get_dynamic_target(target_id: int, _: AdminUser):
    async with get_session() as session:
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            response = _dynamic_to_response(target)
    return response


@router.patch("/dynamic-targets/{target_id}", response_model=DynamicTargetResponse)
async def update_dynamic_target(
    target_id: int, body: DynamicTargetUpdate, _: AdminUser
):
    async with get_session() as session:
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            current_uid = target.uid
            if body.uid is not None:
                uid_for_name = body.uid.strip()
                if not uid_for_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="UID 不能为空",
                    )
                if uid_for_name != current_uid:
                    existing = await session.scalar(
                        select(DynamicTarget).where(DynamicTarget.uid == uid_for_name)
                    )
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="UID already exists",
                        )
            else:
                uid_for_name = current_uid
            if body.name is not None:
                pending_name = body.name.strip() or None
            else:
                pending_name = target.name

        resolved_name: str | None = None
        if not pending_name:
            resolved_name = await resolve_up_name(uid_for_name)
            if not resolved_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法获取 UP 主信息，请检查 UID 是否正确，或手动填写显示名称",
                )

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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )

            if body.uid is not None:
                new_uid = body.uid.strip()
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
            if resolved_name is not None:
                target.name = resolved_name
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
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _dynamic_to_response(target)

    await get_config_service().reload()

    return response


@router.delete("/dynamic-targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dynamic_target(target_id: int, _: AdminUser):
    async with get_session() as session:
        async with session.begin():
            target = await session.get(DynamicTarget, target_id)
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            await session.delete(target)

    await get_config_service().reload()


# --- Live targets ---


@router.get("/live-targets", response_model=list[LiveTargetResponse])
async def list_live_targets(_: AdminUser):
    async with get_session() as session:
        async with session.begin():
            stmt = select(LiveTarget).options(
                selectinload(LiveTarget.groups),
                selectinload(LiveTarget.users),
            )
            targets = (await session.scalars(stmt)).all()
            response = [_live_to_response(t) for t in targets]
            missing = [(t.id, t.room_id) for t in targets if not t.name]

    if missing:
        spawn_background_task(
            "补全直播 target 名称",
            resolve_missing_live_target_names(missing),
        )
    return response


@router.post(
    "/live-targets",
    response_model=LiveTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_live_target(body: LiveTargetCreate, _: AdminUser):
    _ensure_recipients(body.group_ids, body.user_ids)

    async with get_session() as session:
        async with session.begin():
            existing = await session.scalar(
                select(LiveTarget).where(LiveTarget.room_id == body.room_id)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Room already exists"
                )

        resolved_name = await resolve_live_target_name(body.room_id, body.name)
        if not resolved_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取直播间信息，请检查房间号是否正确，或手动填写显示名称",
            )

        async with session.begin():
            existing = await session.scalar(
                select(LiveTarget).where(LiveTarget.room_id == body.room_id)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Room already exists"
                )

            target = LiveTarget(
                room_id=body.room_id,
                name=resolved_name,
                enabled=body.enabled,
                at_all=body.at_all,
            )
            await _sync_groups_live(session, target, body.group_ids)
            await _sync_users_live(session, target, body.user_ids)
            session.add(target)
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _live_to_response(target)

    await get_config_service().reload()

    return response


@router.get("/live-targets/{target_id}", response_model=LiveTargetResponse)
async def get_live_target(target_id: int, _: AdminUser):
    async with get_session() as session:
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            response = _live_to_response(target)
    return response


@router.patch("/live-targets/{target_id}", response_model=LiveTargetResponse)
async def update_live_target(target_id: int, body: LiveTargetUpdate, _: AdminUser):
    async with get_session() as session:
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            current_room_id = target.room_id
            if body.room_id is not None:
                room_id_for_name = body.room_id.strip()
                if not room_id_for_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="房间号不能为空",
                    )
                if room_id_for_name != current_room_id:
                    existing = await session.scalar(
                        select(LiveTarget).where(LiveTarget.room_id == room_id_for_name)
                    )
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Room already exists",
                        )
            else:
                room_id_for_name = current_room_id
            if body.name is not None:
                pending_name = body.name.strip() or None
            else:
                pending_name = target.name

        resolved_name: str | None = None
        if not pending_name:
            resolved_name = await resolve_live_streamer_name(room_id_for_name)
            if not resolved_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法获取直播间信息，请检查房间号是否正确，或手动填写显示名称",
                )

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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )

            if body.room_id is not None:
                new_room_id = body.room_id.strip()
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
            if resolved_name is not None:
                target.name = resolved_name
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
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _live_to_response(target)

    await get_config_service().reload()

    return response


@router.delete("/live-targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_live_target(target_id: int, _: AdminUser):
    async with get_session() as session:
        async with session.begin():
            target = await session.get(LiveTarget, target_id)
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            await session.delete(target)

    await get_config_service().reload()


# --- X targets ---


@router.get("/x-targets", response_model=list[XTargetResponse])
async def list_x_targets(_: AdminUser):
    async with get_session() as session:
        async with session.begin():
            stmt = select(XTarget).options(
                selectinload(XTarget.groups),
                selectinload(XTarget.users),
            )
            targets = (await session.scalars(stmt)).all()
            response = [_x_to_response(t) for t in targets]
            missing = [
                (t.id, t.username) for t in targets if not t.name or not t.user_id
            ]

    if missing:
        spawn_background_task(
            "补全 X target 名称",
            resolve_missing_x_target_names(missing),
        )
    return response


@router.post(
    "/x-targets",
    response_model=XTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_x_target(body: XTargetCreate, _: AdminUser):
    _ensure_recipients(body.group_ids, body.user_ids)
    username = _normalize_x_username(body.username)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空"
        )

    async with get_session() as session:
        async with session.begin():
            existing = await session.scalar(
                select(XTarget).where(XTarget.username == username)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )

        resolved_name, resolved_user_id = await resolve_x_target_name(
            username, body.name
        )
        if not resolved_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取 X 用户信息，请检查用户名与 Bearer Token，或手动填写显示名称",
            )

        async with session.begin():
            existing = await session.scalar(
                select(XTarget).where(XTarget.username == username)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )

            target = XTarget(
                username=username,
                name=resolved_name,
                user_id=resolved_user_id,
                enabled=body.enabled,
                at_all=body.at_all,
            )
            await _sync_groups_x(session, target, body.group_ids)
            await _sync_users_x(session, target, body.user_ids)
            session.add(target)
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _x_to_response(target)

    await get_config_service().reload()

    return response


@router.get("/x-targets/{target_id}", response_model=XTargetResponse)
async def get_x_target(target_id: int, _: AdminUser):
    async with get_session() as session:
        async with session.begin():
            target = await session.scalar(
                select(XTarget)
                .where(XTarget.id == target_id)
                .options(
                    selectinload(XTarget.groups),
                    selectinload(XTarget.users),
                )
            )
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            response = _x_to_response(target)
    return response


@router.patch("/x-targets/{target_id}", response_model=XTargetResponse)
async def update_x_target(target_id: int, body: XTargetUpdate, _: AdminUser):
    async with get_session() as session:
        async with session.begin():
            target = await session.scalar(
                select(XTarget)
                .where(XTarget.id == target_id)
                .options(
                    selectinload(XTarget.groups),
                    selectinload(XTarget.users),
                )
            )
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            current_username = target.username
            if body.username is not None:
                username_for_name = _normalize_x_username(body.username)
                if not username_for_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="用户名不能为空",
                    )
                if username_for_name != current_username:
                    existing = await session.scalar(
                        select(XTarget).where(XTarget.username == username_for_name)
                    )
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Username already exists",
                        )
            else:
                username_for_name = current_username
            if body.name is not None:
                pending_name = body.name.strip() or None
            else:
                pending_name = target.name
            current_user_id = target.user_id

        resolved_name: str | None = None
        resolved_user_id: str | None = None
        if not pending_name or body.username is not None:
            name, user_id = await resolve_x_target_name(
                username_for_name, pending_name
            )
            if not pending_name:
                if not name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="无法获取 X 用户信息，请检查用户名与 Bearer Token，或手动填写显示名称",
                    )
                resolved_name = name
            resolved_user_id = user_id
        elif not current_user_id:
            user = await resolve_x_user(username_for_name)
            if user:
                resolved_user_id = user.id

        async with session.begin():
            target = await session.scalar(
                select(XTarget)
                .where(XTarget.id == target_id)
                .options(
                    selectinload(XTarget.groups),
                    selectinload(XTarget.users),
                )
            )
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )

            if body.username is not None:
                new_username = _normalize_x_username(body.username)
                if new_username != target.username:
                    existing = await session.scalar(
                        select(XTarget).where(XTarget.username == new_username)
                    )
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Username already exists",
                        )
                    target.username = new_username

            if body.name is not None:
                stripped = body.name.strip()
                target.name = stripped if stripped else None
            if resolved_name is not None:
                target.name = resolved_name
            if resolved_user_id is not None:
                target.user_id = resolved_user_id
            if body.enabled is not None:
                target.enabled = body.enabled
            if body.at_all is not None:
                target.at_all = body.at_all
            if body.group_ids is not None:
                await _sync_groups_x(session, target, body.group_ids)
            if body.user_ids is not None:
                await _sync_users_x(session, target, body.user_ids)
            if body.group_ids is not None or body.user_ids is not None:
                _ensure_recipients(
                    [g.group_id for g in target.groups],
                    [u.user_id for u in target.users],
                )
            await session.flush()
            await session.refresh(target, ["groups", "users"])
            response = _x_to_response(target)

    await get_config_service().reload()

    return response


@router.delete("/x-targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_x_target(target_id: int, _: AdminUser):
    async with get_session() as session:
        async with session.begin():
            target = await session.get(XTarget, target_id)
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
                )
            await session.delete(target)

    await get_config_service().reload()
