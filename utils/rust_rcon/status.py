"""Parse Rust server ``status`` RCON output for online Steam IDs."""

from __future__ import annotations

import re

_STEAM_ID64_BODY = r"7656119\d{10}"
_STEAM_ID64_IN_TEXT_RE = re.compile(rf"\b{_STEAM_ID64_BODY}\b")


def parse_online_steam_ids(status_text: str) -> set[str]:
    return set(_STEAM_ID64_IN_TEXT_RE.findall(status_text or ""))


def is_steam_id_online(status_text: str, steam_id: str) -> bool:
    from shared.config.rust_player import STEAM_ID64_RE

    steam_id = str(steam_id).strip()
    if not STEAM_ID64_RE.fullmatch(steam_id):
        return False
    return steam_id in parse_online_steam_ids(status_text)
