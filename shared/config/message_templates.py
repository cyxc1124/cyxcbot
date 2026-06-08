"""Default push message templates and setting keys."""

from __future__ import annotations

from dataclasses import dataclass

DYNAMIC_TEMPLATE_KEYS = {
    "dynamic_template_push": "{name} {type_desc}\n{time}\n{media}\n{url}",
    "dynamic_template_pinned": "{name} 置顶了动态\n{time}\n{media}\n{url}",
    "dynamic_template_query_latest": "【{name} 的最新动态】\n{media}\n{url}",
    "dynamic_template_query_pinned": "【{name} 的置顶动态】\n{media}\n{url}",
}

LIVE_TEMPLATE_KEYS = {
    "live_template_start": "{streamer_name} 开播啦！\n{card}\n{url}",
    "live_template_end": "【下播提醒】\n{streamer_name}下播啦！\n{card}\n直播时长：{duration}",
}

MESSAGE_TEMPLATE_KEYS = {**DYNAMIC_TEMPLATE_KEYS, **LIVE_TEMPLATE_KEYS}

MAX_TEMPLATE_LENGTH = 500


@dataclass
class DynamicMessageTemplates:
    push: str = DYNAMIC_TEMPLATE_KEYS["dynamic_template_push"]
    pinned: str = DYNAMIC_TEMPLATE_KEYS["dynamic_template_pinned"]
    query_latest: str = DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_latest"]
    query_pinned: str = DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_pinned"]


@dataclass
class LiveMessageTemplates:
    start: str = LIVE_TEMPLATE_KEYS["live_template_start"]
    end: str = LIVE_TEMPLATE_KEYS["live_template_end"]


def dynamic_templates_from_settings(settings: dict[str, str]) -> DynamicMessageTemplates:
    return DynamicMessageTemplates(
        push=settings.get("dynamic_template_push", DYNAMIC_TEMPLATE_KEYS["dynamic_template_push"]),
        pinned=settings.get(
            "dynamic_template_pinned",
            DYNAMIC_TEMPLATE_KEYS["dynamic_template_pinned"],
        ),
        query_latest=settings.get(
            "dynamic_template_query_latest",
            DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_latest"],
        ),
        query_pinned=settings.get(
            "dynamic_template_query_pinned",
            DYNAMIC_TEMPLATE_KEYS["dynamic_template_query_pinned"],
        ),
    )


def _resolve_live_end_template(settings: dict[str, str]) -> str:
    end = settings.get("live_template_end", "").strip()
    if end:
        return end

    header = settings.get("live_template_end_header", "").strip()
    duration = settings.get("live_template_end_duration", "").strip()
    if header and duration and "{duration}" not in header:
        return f"{header}\n{duration}"
    if header:
        return header
    return LIVE_TEMPLATE_KEYS["live_template_end"]


def live_templates_from_settings(settings: dict[str, str]) -> LiveMessageTemplates:
    return LiveMessageTemplates(
        start=settings.get("live_template_start", LIVE_TEMPLATE_KEYS["live_template_start"]),
        end=_resolve_live_end_template(settings),
    )
