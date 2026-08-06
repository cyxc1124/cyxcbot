"""Rust RCON custom command CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from admin.deps import AdminUser, RequireSetup
from admin.schemas.rust_rcon_custom import (
    RustRconCustomCommandCreateRequest,
    RustRconCustomCommandListResponse,
    RustRconCustomCommandResponse,
    RustRconCustomCommandUpdateRequest,
)
from shared.config.rust_rcon import normalize_allowed_qq_ids
from shared.config.rust_rcon_custom import custom_command_name_conflict
from shared.config.service import get_config_service
from shared.db.models import (
    RustRconBinding,
    RustRconCustomCommand,
    RustRconCustomCommandAllowedUser,
)

router = APIRouter(
    prefix="/rust-rcon/custom-commands",
    tags=["rust-rcon-custom-commands"],
    dependencies=[RequireSetup],
)


def _allowed_qq_ids(row: RustRconCustomCommand) -> list[str]:
    return sorted(
        {str(item.user_id) for item in row.allowed_users},
        key=lambda value: (not value.isdigit(), value),
    )


def _to_response(row: RustRconCustomCommand) -> RustRconCustomCommandResponse:
    return RustRconCustomCommandResponse(
        id=row.id,
        name=row.name,
        template=row.template,
        binding_id=row.binding_id,
        enabled=row.enabled,
        allowed_qq_ids=_allowed_qq_ids(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _ensure_binding_exists(session, binding_id: int) -> None:
    binding = await session.get(RustRconBinding, int(binding_id))
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RCON 绑定不存在",
        )


async def _sync_allowed_users(
    session, row: RustRconCustomCommand, allowed_qq_ids: list[str]
) -> None:
    normalized = normalize_allowed_qq_ids(allowed_qq_ids)
    for item in list(row.allowed_users):
        await session.delete(item)
    await session.flush()
    row.allowed_users = [
        RustRconCustomCommandAllowedUser(user_id=qq) for qq in normalized
    ]


def _ensure_name_available(name: str, *, exclude_id: int | None = None) -> None:
    conflict = custom_command_name_conflict(
        name,
        get_config_service().get_snapshot(),
        exclude_id=exclude_id,
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict,
        )


@router.get("", response_model=RustRconCustomCommandListResponse)
async def list_rust_rcon_custom_commands(
    _: AdminUser,
) -> RustRconCustomCommandListResponse:
    async with get_session() as session:
        async with session.begin():
            rows = (
                await session.scalars(
                    select(RustRconCustomCommand)
                    .options(selectinload(RustRconCustomCommand.allowed_users))
                    .order_by(RustRconCustomCommand.id)
                )
            ).all()
            return RustRconCustomCommandListResponse(
                items=[_to_response(row) for row in rows]
            )


@router.post(
    "",
    response_model=RustRconCustomCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rust_rcon_custom_command(
    body: RustRconCustomCommandCreateRequest,
    _: AdminUser,
) -> RustRconCustomCommandResponse:
    _ensure_name_available(body.name)

    try:
        async with get_session() as session:
            async with session.begin():
                await _ensure_binding_exists(session, body.binding_id)
                row = RustRconCustomCommand(
                    name=body.name,
                    template=body.template,
                    binding_id=body.binding_id,
                    enabled=body.enabled,
                    allowed_users=[
                        RustRconCustomCommandAllowedUser(user_id=qq)
                        for qq in body.allowed_qq_ids
                    ],
                )
                session.add(row)
                await session.flush()
                await session.refresh(row, ["allowed_users"])
                response = _to_response(row)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"指令名「{body.name}」已存在",
        ) from exc

    await get_config_service().reload()
    return response


@router.patch("/{command_id}", response_model=RustRconCustomCommandResponse)
async def update_rust_rcon_custom_command(
    command_id: int,
    body: RustRconCustomCommandUpdateRequest,
    _: AdminUser,
) -> RustRconCustomCommandResponse:
    try:
        async with get_session() as session:
            async with session.begin():
                row = (
                    await session.scalars(
                        select(RustRconCustomCommand)
                        .where(RustRconCustomCommand.id == command_id)
                        .options(selectinload(RustRconCustomCommand.allowed_users))
                    )
                ).first()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="自定义指令不存在",
                    )

                if body.name is not None and body.name != row.name:
                    row.name = body.name
                if body.template is not None:
                    row.template = body.template
                if body.binding_id is not None:
                    await _ensure_binding_exists(session, body.binding_id)
                    row.binding_id = body.binding_id
                if body.enabled is not None:
                    row.enabled = body.enabled
                if body.allowed_qq_ids is not None:
                    await _sync_allowed_users(session, row, body.allowed_qq_ids)

                # 启用中的指令始终按最终 name 复核冲突（含仅打开开关的路径）。
                if row.enabled:
                    _ensure_name_available(row.name, exclude_id=command_id)

                await session.flush()
                await session.refresh(row, ["allowed_users"])
                response = _to_response(row)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="指令名已存在",
        ) from exc

    await get_config_service().reload()
    return response


@router.delete("/{command_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rust_rcon_custom_command(command_id: int, _: AdminUser) -> None:
    async with get_session() as session:
        async with session.begin():
            row = await session.get(RustRconCustomCommand, command_id)
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="自定义指令不存在",
                )
            await session.delete(row)

    await get_config_service().reload()
