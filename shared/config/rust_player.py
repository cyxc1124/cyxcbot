"""Rust player command parsing and SteamID validation."""

from __future__ import annotations

import re

STEAM_ID64_RE = re.compile(r"^7656119\d{10}$")
BIND_TRIGGER = "绑定"
CHECKIN_TRIGGER = "签到"
POINTS_TRIGGERS = ("我的积分", "积分")


def _strip_command_prefix(text: str) -> str | None:
    prefixes: set[str] = {"/"}
    try:
        from nonebot import get_driver

        starts = {str(s) for s in get_driver().config.command_start if s}
        if starts:
            prefixes = starts
    except Exception:
        pass
    try:
        from shared.config.service import get_config_service

        prefixes |= set(get_config_service().get_snapshot().command_extra_prefixes)
    except Exception:
        pass
    for prefix in sorted(prefixes, key=len, reverse=True):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return None


def _message_candidates(text: str) -> list[str]:
    text = text.strip()
    candidates = [text]
    stripped = _strip_command_prefix(text)
    if stripped is not None:
        candidates.append(stripped.strip())
    return candidates


def normalize_steam_id(raw: str) -> str | None:
    steam_id = str(raw).strip()
    if STEAM_ID64_RE.fullmatch(steam_id):
        return steam_id
    return None


def is_bind_command(text: str) -> bool:
    for candidate in _message_candidates(text):
        if candidate == BIND_TRIGGER:
            return True
        if candidate.startswith(BIND_TRIGGER) and len(candidate) > len(BIND_TRIGGER):
            if candidate[len(BIND_TRIGGER)].isspace():
                return True
    return False


def parse_bind_steam_id(text: str) -> str | None:
    """Match ``绑定 <steamid64>``; return steam id or None."""
    for candidate in _message_candidates(text):
        if not candidate.startswith(BIND_TRIGGER):
            continue
        if len(candidate) <= len(BIND_TRIGGER):
            continue
        if not candidate[len(BIND_TRIGGER)].isspace():
            continue
        steam_id = normalize_steam_id(candidate[len(BIND_TRIGGER) :].strip())
        if steam_id is not None:
            return steam_id
    return None


def is_checkin_command(text: str) -> bool:
    for candidate in _message_candidates(text):
        if candidate == CHECKIN_TRIGGER:
            return True
    return False


def is_points_query_command(text: str) -> bool:
    for candidate in _message_candidates(text):
        if candidate in POINTS_TRIGGERS:
            return True
    return False


def normalize_checkin_points_range(min_points: int, max_points: int) -> tuple[int, int]:
    min_val = int(min_points)
    max_val = int(max_points)
    if min_val < 0 or max_val < 0:
        raise ValueError("积分不能为负数")
    if min_val > max_val:
        raise ValueError("最小积分不能大于最大积分")
    if max_val > 1_000_000:
        raise ValueError("积分上限过大")
    return min_val, max_val
