"""Rust RCON binding CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from admin.deps import AdminUser, RequireSetup
from admin.schemas.rust_rcon import (
    RustRconBindingCreate,
    RustRconBindingResponse,
    RustRconBindingUpdate,
    RustRconPasswordStatus,
)
from shared.config.rust_rcon import (
    alias_command_conflict,
    normalize_alias,
    normalize_allowed_qq_ids,
    normalize_port,
)
from shared.config.service import get_config_service
from shared.db.models import RustRconBinding, RustRconBindingAllowedUser
from shared.security.crypto import encrypt_value, mask_secret

router = APIRouter(
    prefix="/rust-rcon/bindings",
    tags=["rust-rcon"],
    dependencies=[RequireSetup],
)


def _password_status(encrypted: str, decrypted: str = "") -> RustRconPasswordStatus:
    if not encrypted:
        return RustRconPasswordStatus(configured=False, preview=None)
    preview = mask_secret(decrypted) if decrypted else None
    return RustRconPasswordStatus(configured=True, preview=preview or "****")


def _allowed_qq_ids(row: RustRconBinding) -> list[str]:
    return sorted(
        {str(item.user_id) for item in row.allowed_users},
        key=lambda value: (not value.isdigit(), value),
    )


def _to_response(row: RustRconBinding, decrypted: str = "") -> RustRconBindingResponse:
    return RustRconBindingResponse(
        id=row.id,
        alias=row.alias,
        host=row.host,
        port=row.port,
        password=_password_status(row.password_encrypted, decrypted),
        enabled=row.enabled,
        name=row.name,
        allowed_qq_ids=_allowed_qq_ids(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _sync_allowed_users(
    session, row: RustRconBinding, allowed_qq_ids: list[str]
) -> None:
    normalized = normalize_allowed_qq_ids(allowed_qq_ids)
    for item in list(row.allowed_users):
        await session.delete(item)
    await session.flush()
    row.allowed_users = [RustRconBindingAllowedUser(user_id=qq) for qq in normalized]


def _ensure_alias_available(
    alias: str,
    *,
    exclude_id: int | None = None,
    require_command_clear: bool = True,
) -> None:
    svc = get_config_service()
    snap = svc.get_snapshot()
    if require_command_clear:
        conflict = alias_command_conflict(alias, snap)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=conflict
            )

    for binding in snap.rust_rcon_bindings:
        if binding.alias == alias and binding.id != exclude_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"触发词「{alias}」已被其他 RCON 绑定使用",
            )


@router.get("", response_model=list[RustRconBindingResponse])
async def list_rust_rcon_bindings(_: AdminUser):
    session = get_session()
    async with session.begin():
        stmt = select(RustRconBinding).options(
            selectinload(RustRconBinding.allowed_users)
        )
        rows = (await session.scalars(stmt)).all()
        snap = get_config_service().get_snapshot()
        by_id = {item.id: item.password for item in snap.rust_rcon_bindings}
        return [_to_response(row, by_id.get(row.id, "")) for row in rows]


@router.post(
    "",
    response_model=RustRconBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rust_rcon_binding(body: RustRconBindingCreate, _: AdminUser):
    try:
        alias = normalize_alias(body.alias)
        port = normalize_port(body.port)
        allowed_qq_ids = normalize_allowed_qq_ids(body.allowed_qq_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    host = body.host.strip()
    if not host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="主机地址不能为空"
        )

    _ensure_alias_available(alias, require_command_clear=body.enabled)

    session = get_session()
    async with session.begin():
        existing = await session.scalar(
            select(RustRconBinding).where(RustRconBinding.alias == alias)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"触发词「{alias}」已存在",
            )

        row = RustRconBinding(
            alias=alias,
            host=host,
            port=port,
            password_encrypted=encrypt_value(body.password),
            enabled=body.enabled,
            name=(body.name.strip() if body.name else None) or None,
        )
        row.allowed_users = [
            RustRconBindingAllowedUser(user_id=qq) for qq in allowed_qq_ids
        ]
        session.add(row)
        await session.flush()
        await session.refresh(row, ["allowed_users"])
        response = _to_response(row, body.password)

    await get_config_service().reload()
    return response


@router.patch("/{binding_id}", response_model=RustRconBindingResponse)
async def update_rust_rcon_binding(
    binding_id: int, body: RustRconBindingUpdate, _: AdminUser
):
    session = get_session()
    async with session.begin():
        row = await session.scalar(
            select(RustRconBinding)
            .where(RustRconBinding.id == binding_id)
            .options(selectinload(RustRconBinding.allowed_users))
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="RCON 绑定不存在"
            )

        was_enabled = row.enabled

        decrypted = ""
        snap = get_config_service().get_snapshot()
        for item in snap.rust_rcon_bindings:
            if item.id == binding_id:
                decrypted = item.password
                break

        if body.alias is not None:
            try:
                alias = normalize_alias(body.alias)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            if alias != row.alias:
                _ensure_alias_available(
                    alias,
                    exclude_id=binding_id,
                    require_command_clear=(was_enabled or body.enabled is True),
                )
                row.alias = alias

        if body.host is not None:
            host = body.host.strip()
            if not host:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="主机地址不能为空"
                )
            row.host = host

        if body.port is not None:
            try:
                row.port = normalize_port(body.port)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc

        if body.password is not None and body.password.strip():
            decrypted = body.password
            row.password_encrypted = encrypt_value(body.password)

        if body.enabled is not None:
            row.enabled = body.enabled

        if row.enabled and not was_enabled:
            _ensure_alias_available(row.alias, exclude_id=binding_id)

        if body.name is not None:
            row.name = body.name.strip() or None

        if body.allowed_qq_ids is not None:
            try:
                await _sync_allowed_users(session, row, body.allowed_qq_ids)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc

        await session.flush()
        await session.refresh(row, ["allowed_users"])
        response = _to_response(row, decrypted)

    await get_config_service().reload()
    return response


@router.delete("/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rust_rcon_binding(binding_id: int, _: AdminUser):
    session = get_session()
    async with session.begin():
        row = await session.get(RustRconBinding, binding_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="RCON 绑定不存在"
            )
        await session.delete(row)

    await get_config_service().reload()
