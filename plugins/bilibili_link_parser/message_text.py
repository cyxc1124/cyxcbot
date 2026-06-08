"""Extract searchable text and URLs from QQ messages."""

from __future__ import annotations

import json
import re
from typing import Iterable

from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _urls_from_json_payload(payload: object) -> list[str]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            if "bilibili.com" in value or "b23.tv" in value:
                found.append(value)
            found.extend(_URL_IN_TEXT.findall(value))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


def _urls_from_json_segment(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _URL_IN_TEXT.findall(raw)
    return _urls_from_json_payload(payload)


def _urls_from_xml_segment(raw: str) -> list[str]:
    if not raw:
        return []
    return [url for url in _URL_IN_TEXT.findall(raw) if "bilibili.com" in url or "b23.tv" in url]


def collect_message_text(event: GroupMessageEvent | PrivateMessageEvent) -> str:
    """Collect plain text plus bilibili-related URLs from structured segments."""
    parts: list[str] = []

    plain = event.get_plaintext().strip()
    if plain:
        parts.append(plain)

    for segment in event.message:
        if segment.type == "json":
            urls = _urls_from_json_segment(str(segment.data.get("data", "")))
            parts.extend(urls)
        elif segment.type == "xml":
            parts.extend(_urls_from_xml_segment(str(segment.data.get("data", ""))))

    return "\n".join(_dedupe_preserve_order(parts))


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
