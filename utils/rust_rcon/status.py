"""Parse Rust server ``status`` RCON output for online Steam IDs."""

from __future__ import annotations

import re

_STEAM_ID64_BODY = r"7656119\d{10}"
# status player rows start with SteamID64 in the id column, e.g.:
# 76561198000000001 "Alice" 28 300.99s 127.0.0.1:12345 0 0.0 0
_STATUS_PLAYER_ID_RE = re.compile(rf"^\s*({_STEAM_ID64_BODY})(?:\s|$)")
_STATUS_PLAYER_ROW_RE = re.compile(rf'^\s*({_STEAM_ID64_BODY})\s+"([^"]*)"')


def parse_online_steam_ids(status_text: str) -> set[str]:
    ids: set[str] = set()
    for line in (status_text or "").splitlines():
        match = _STATUS_PLAYER_ID_RE.match(line)
        if match is not None:
            ids.add(match.group(1))
    return ids


def get_player_display_name(status_text: str, steam_id: str) -> str | None:
    steam_id = str(steam_id).strip()
    for line in (status_text or "").splitlines():
        match = _STATUS_PLAYER_ROW_RE.match(line)
        if match is not None and match.group(1) == steam_id:
            return match.group(2)
    return None


def player_display_name_contains_code(
    status_text: str, steam_id: str, verify_code: str
) -> bool:
    name = get_player_display_name(status_text, steam_id)
    if not name:
        return False
    code = str(verify_code).strip().upper()
    if not code:
        return False
    return code in name.upper()


def is_steam_id_online(status_text: str, steam_id: str) -> bool:
    from shared.config.rust_player import STEAM_ID64_RE

    steam_id = str(steam_id).strip()
    if not STEAM_ID64_RE.fullmatch(steam_id):
        return False
    return steam_id in parse_online_steam_ids(status_text)
