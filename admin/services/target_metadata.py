"""Resolve Bilibili display names for monitor targets."""

from __future__ import annotations

import aiohttp
from nonebot.log import logger

from shared.config.service import get_config_service
from shared.db.models import DynamicTarget, LiveTarget
from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.live_api import LiveApi


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

    db = get_session()
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

    db = get_session()
    async with db.begin():
        for target_id, room_id, name in resolved:
            target = await db.get(LiveTarget, target_id)
            if target is not None and not target.name and target.room_id == room_id:
                target.name = name
