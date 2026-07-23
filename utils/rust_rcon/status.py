"""Parse Rust server ``status`` RCON output for online Steam IDs."""

from __future__ import annotations

import re

_STEAM_ID64_BODY = r"7656119\d{10}"
# status player rows start with SteamID64 in the id column, e.g.:
# 76561198000000001 "Alice" 28 300.99s 127.0.0.1:12345 0 0.0 0
_STATUS_PLAYER_ID_RE = re.compile(rf"^\s*({_STEAM_ID64_BODY})(?:\s|$)")


def parse_online_steam_ids(status_text: str) -> set[str]:
    ids: set[str] = set()
    for line in (status_text or "").splitlines():
        match = _STATUS_PLAYER_ID_RE.match(line)
        if match is not None:
            ids.add(match.group(1))
    return ids


def is_steam_id_online(status_text: str, steam_id: str) -> bool:
    from shared.config.rust_player import STEAM_ID64_RE

    steam_id = str(steam_id).strip()
    if not STEAM_ID64_RE.fullmatch(steam_id):
        return False
    return steam_id in parse_online_steam_ids(status_text)
