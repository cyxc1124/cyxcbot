"""Resolve Bilibili / X display names for monitor targets."""

from __future__ import annotations

from typing import Optional

import aiohttp
from nonebot.log import logger

from shared.config.proxy import ProxyConfig
from shared.config.service import get_config_service
from shared.db.models import DynamicTarget, LiveTarget, XTarget
from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.live_api import LiveApi
from utils.x_api import XApiClient, XUser, create_session


def _bilibili_cookie() -> str | None:
    cookie = get_config_service().get_snapshot().bilibili_cookie
    return cookie or None


async def _resolve_up_name_with_session(
    session: aiohttp.ClientSession, uid: str
) -> str | None:
    fetcher = DynamicFetcher(session, _bilibili_cookie())
    return await fetcher._get_user_name_from_api(uid)


async def _resolve_live_streamer_name_with_session(
    session: aiohttp.ClientSession, room_id: str
) -> str | None:
    try:
        rid = int(room_id)
    except ValueError:
        return None
    api = LiveApi(session, _bilibili_cookie())
    _, user_info = await api.get_room_and_user_info(rid)
    if user_info and user_info.name:
        return user_info.name
    return None


async def resolve_up_name(
    uid: str, *, session: aiohttp.ClientSession | None = None
) -> str | None:
    """Fetch UP主 nickname by UID."""
    uid = str(uid).strip()
    if not uid:
        return None
    try:
        if session is not None:
            return await _resolve_up_name_with_session(session, uid)
        async with aiohttp.ClientSession() as own_session:
            return await _resolve_up_name_with_session(own_session, uid)
    except Exception as exc:
        logger.warning("解析 UP 主 {} 昵称失败: {}", uid, exc)
        return None


async def resolve_live_streamer_name(
    room_id: str, *, session: aiohttp.ClientSession | None = None
) -> str | None:
    """Fetch streamer nickname by live room id."""
    room_id = str(room_id).strip()
    if not room_id:
        return None
    try:
        if session is not None:
            return await _resolve_live_streamer_name_with_session(session, room_id)
        async with aiohttp.ClientSession() as own_session:
            return await _resolve_live_streamer_name_with_session(own_session, room_id)
    except Exception as exc:
        logger.warning("解析直播间 {} 主播昵称失败: {}", room_id, exc)
    return None


async def resolve_dynamic_target_name(
    uid: str, manual_name: str | None = None
) -> str | None:
    """Prefer manual name; otherwise fetch from Bilibili."""
    if manual_name and manual_name.strip():
        return manual_name.strip()
    return await resolve_up_name(uid)


async def resolve_live_target_name(
    room_id: str, manual_name: str | None = None
) -> str | None:
    """Prefer manual name; otherwise fetch streamer nickname."""
    if manual_name and manual_name.strip():
        return manual_name.strip()
    return await resolve_live_streamer_name(room_id)


async def resolve_missing_dynamic_target_names(
    items: list[tuple[int, str]],
) -> None:
    """Background: resolve and persist missing dynamic target display names."""
    if not items:
        return
    resolved: list[tuple[int, str, str]] = []
    try:
        async with aiohttp.ClientSession() as http_session:
            for target_id, uid in items:
                name = await _resolve_up_name_with_session(http_session, uid)
                if name:
                    resolved.append((target_id, uid, name))
    except Exception as exc:
        logger.warning("批量解析动态 target 名称失败: {}", exc)
        return
    if not resolved:
        return
    from nonebot_plugin_orm import get_session

    async with get_session() as db:
        async with db.begin():
            for target_id, uid, name in resolved:
                target = await db.get(DynamicTarget, target_id)
                if target is not None and not target.name and target.uid == uid:
                    target.name = name


async def resolve_missing_live_target_names(
    items: list[tuple[int, str]],
) -> None:
    """Background: resolve and persist missing live target display names."""
    if not items:
        return
    resolved: list[tuple[int, str, str]] = []
    try:
        async with aiohttp.ClientSession() as http_session:
            for target_id, room_id in items:
                name = await _resolve_live_streamer_name_with_session(
                    http_session, room_id
                )
                if name:
                    resolved.append((target_id, room_id, name))
    except Exception as exc:
        logger.warning("批量解析直播 target 名称失败: {}", exc)
        return
    if not resolved:
        return
    from nonebot_plugin_orm import get_session

    async with get_session() as db:
        async with db.begin():
            for target_id, room_id, name in resolved:
                target = await db.get(LiveTarget, target_id)
                if target is not None and not target.name and target.room_id == room_id:
                    target.name = name


def _x_proxy_and_bearer() -> tuple[ProxyConfig, str]:
    snap = get_config_service().get_snapshot()
    return snap.x_proxy, snap.x_api_bearer


def _x_http_proxy_url(proxy: ProxyConfig) -> str | None:
    if proxy.is_configured and proxy.scheme in ("http", "https"):
        return proxy.to_url()
    return None


async def resolve_x_user(username: str) -> Optional[XUser]:
    """Fetch X user by username (without @)."""
    key = (username or "").strip().lstrip("@").strip()
    if not key:
        return None
    proxy, bearer = _x_proxy_and_bearer()
    if not bearer:
        logger.warning("解析 X 用户失败: 未配置 Bearer Token")
        return None
    try:
        session = create_session(proxy)
        async with session:
            client = XApiClient(session, bearer, proxy_url=_x_http_proxy_url(proxy))
            return await client.get_user_by_username(key)
    except Exception as exc:
        logger.warning("解析 X 用户 {} 失败: {}", key, exc)
        return None


async def resolve_x_username_display_name(username: str) -> Optional[str]:
    """Fetch X display name by username."""
    user = await resolve_x_user(username)
    if not user:
        return None
    return (user.name or user.username or "").strip() or None


async def resolve_x_target_name(
    username: str, manual_name: str | None = None
) -> tuple[Optional[str], Optional[str]]:
    """Prefer manual name; also resolve X user_id.

    Returns (display_name, user_id). Display name may come from manual input
    even when API lookup fails; both None means unusable.
    """
    user = await resolve_x_user(username)
    user_id = user.id if user else None
    if manual_name and manual_name.strip():
        return manual_name.strip(), user_id
    if user:
        name = (user.name or user.username or "").strip() or None
        return name, user_id
    return None, None


async def resolve_missing_x_target_names(
    items: list[tuple[int, str]],
) -> None:
    """Background: resolve and persist missing X target display names / user_ids."""
    if not items:
        return
    resolved: list[tuple[int, str, str, str | None]] = []
    try:
        for target_id, username in items:
            user = await resolve_x_user(username)
            if not user:
                continue
            name = (user.name or user.username or "").strip()
            if name:
                resolved.append((target_id, username, name, user.id))
    except Exception as exc:
        logger.warning("批量解析 X target 名称失败: {}", exc)
        return
    if not resolved:
        return
    from nonebot_plugin_orm import get_session

    async with get_session() as db:
        async with db.begin():
            for target_id, username, name, user_id in resolved:
                target = await db.get(XTarget, target_id)
                if target is None or target.username != username:
                    continue
                if not target.name:
                    target.name = name
                if user_id and not target.user_id:
                    target.user_id = user_id
