"""Extract searchable text and Douyin URLs from QQ messages."""

from __future__ import annotations

import re
from typing import Any, Iterable

from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from utils.douyin_api.validators import extract_douyin_urls

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _parse_json_segment_data(raw: str | dict[str, Any]) -> object | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        import json

        return json.loads(raw)
    except Exception:
        return None


def _urls_from_payload(payload: object) -> list[str]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            found.extend(extract_douyin_urls(value))
            for url in _URL_IN_TEXT.findall(value):
                found.extend(extract_douyin_urls(url))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


def collect_message_text(event: GroupMessageEvent | PrivateMessageEvent) -> str:
    parts: list[str] = []

    plain = event.get_plaintext().strip()
    if plain:
        parts.append(plain)

    for segment in event.message:
        if segment.type == "json":
            segment_data = segment.data.get("data", segment.data)
            payload = _parse_json_segment_data(segment_data)
            if isinstance(payload, dict):
                prompt = str(payload.get("prompt", "")).strip()
                if prompt and prompt not in parts:
                    parts.append(prompt)
            if payload is not None:
                parts.extend(_urls_from_payload(payload))
            elif isinstance(segment_data, str):
                parts.extend(extract_douyin_urls(segment_data))
        elif segment.type == "xml":
            raw = str(segment.data.get("data", ""))
            parts.extend(extract_douyin_urls(raw))

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
