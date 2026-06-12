"""Resolve Bilibili display names for monitor targets."""

from __future__ import annotations

import logging

import aiohttp

from shared.config.service import get_config_service
from utils.bilibili_api.dynamic_api import DynamicFetcher
from utils.bilibili_api.live_api import LiveApi

logger = logging.getLogger(__name__)


def _bilibili_cookie() -> str | None:
    cookie = get_config_service().get_snapshot().bilibili_cookie
    return cookie or None


async def resolve_up_name(uid: str) -> str | None:
    """Fetch UP主 nickname by UID."""
    uid = str(uid).strip()
    if not uid:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            fetcher = DynamicFetcher(session, _bilibili_cookie())
            return await fetcher._get_user_name_from_api(uid)
    except Exception as exc:
        logger.warning("Failed to resolve UP name for %s: %s", uid, exc)
        return None


async def resolve_live_streamer_name(room_id: str) -> str | None:
    """Fetch streamer nickname by live room id."""
    room_id = str(room_id).strip()
    if not room_id:
        return None
    try:
        rid = int(room_id)
    except ValueError:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            api = LiveApi(session, _bilibili_cookie())
            _, user_info = await api.get_room_and_user_info(rid)
            if user_info and user_info.name:
                return user_info.name
    except Exception as exc:
        logger.warning(
            "Failed to resolve live streamer name for room %s: %s", room_id, exc
        )
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
