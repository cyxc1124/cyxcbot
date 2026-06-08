"""Extract Bilibili links from QQ mini-app share cards."""

from __future__ import annotations

import json
import re
from typing import Any

_BILIBILI_MINIAPP_APP = "com.tencent.miniapp_01"
_BILIBILI_EXTRA_APPIDS = {100951776}
_BILIBILI_DETAIL_APPIDS = {"1109937557"}
_BILIBILI_HINT = re.compile(r"哔哩哔哩|bilibili", re.IGNORECASE)
_BVID = re.compile(r"BV1[a-zA-Z0-9]{9}")
_URL_KEYS = ("qqdocurl", "url", "jumpUrl", "targetUrl", "action")


def parse_json_segment_data(data: Any) -> object | None:
    """Parse OneBot json segment data that may be nested or pre-parsed."""
    if isinstance(data, dict):
        inner = data.get("data")
        if inner is not None:
            if isinstance(inner, dict):
                return inner
            if isinstance(inner, str):
                return _parse_json_string(inner)
        if "app" in data or "meta" in data:
            return data
        return data
    if isinstance(data, str):
        return _parse_json_string(data)
    return None


def extract_bilibili_miniapp_urls(payload: object) -> list[str]:
    """Extract bilibili video/live URLs from a QQ mini-app JSON payload."""
    if not isinstance(payload, dict):
        return []

    if not _should_scan_qq_share_card(payload):
        return []

    found: list[str] = []
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for detail in meta.values():
            if isinstance(detail, dict):
                found.extend(_urls_from_detail(payload, detail))

    return _dedupe_preserve_order(
        url for url in found if _looks_bilibili_related(url) or _BVID.fullmatch(url)
    )


def normalize_bilibili_url(raw: str) -> str | None:
    """Unescape and normalize a bilibili-related URL or identifier."""
    value = raw.replace("\\/", "/").replace("\\", "").strip().strip('"')
    if not value:
        return None

    if _BVID.fullmatch(value):
        return value

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith(("b23.tv/", "www.b23.tv/")):
        return f"https://{value.removeprefix('www.')}"

    if "bilibili.com" in value or "b23.tv" in value:
        return f"https://{value.lstrip('/')}"

    return None


def _parse_json_string(raw: str) -> object | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _should_scan_qq_share_card(payload: dict) -> bool:
    app = payload.get("app")
    if app in (_BILIBILI_MINIAPP_APP, "com.tencent.structmsg"):
        return True

    prompt = str(payload.get("prompt", ""))
    if prompt.startswith(("[QQ小程序]", "[分享]")):
        return True

    return isinstance(payload.get("meta"), dict)


def _has_bilibili_share_hints(payload: dict, detail: dict) -> bool:
    if _BILIBILI_HINT.search(str(payload.get("desc", ""))):
        return True
    if _BILIBILI_HINT.search(str(payload.get("prompt", ""))):
        return True

    extra = payload.get("extra")
    if isinstance(extra, dict) and extra.get("appid") in _BILIBILI_EXTRA_APPIDS:
        return True

    if str(detail.get("appid", "")) in _BILIBILI_DETAIL_APPIDS:
        return True
    if _BILIBILI_HINT.search(str(detail.get("title", ""))):
        return True

    qqdocurl = detail.get("qqdocurl")
    if isinstance(qqdocurl, str):
        cleaned = qqdocurl.replace("\\/", "/")
        if _looks_bilibili_related(cleaned):
            return True

    return False


def _urls_from_detail(payload: dict, detail: dict) -> list[str]:
    found: list[str] = []
    hints = _has_bilibili_share_hints(payload, detail)

    for key in _URL_KEYS:
        value = detail.get(key)
        if isinstance(value, str):
            if key == "qqdocurl":
                found.extend(_unwrap_qqdocurl(value))
            elif hints:
                normalized = normalize_bilibili_url(value)
                if normalized and _looks_bilibili_related(normalized):
                    found.append(normalized)

    if hints:
        template = detail.get("shareTemplateData")
        if isinstance(template, dict):
            found.extend(_urls_from_share_template(template))
        for key in ("room_id", "roomId", "live_room_id", "roomid"):
            value = detail.get(key)
            if value is not None and str(value).isdigit():
                found.append(f"https://live.bilibili.com/{int(value)}")

    return found


def _unwrap_qqdocurl(raw: str) -> list[str]:
    cleaned = raw.replace("\\/", "/").replace("\\", "").strip()
    if not cleaned:
        return []

    if cleaned.startswith(("http://", "https://")):
        normalized = normalize_bilibili_url(cleaned)
        return [normalized] if normalized and _looks_bilibili_related(normalized) else []

    if cleaned.startswith("b23.tv/"):
        normalized = normalize_bilibili_url(cleaned)
        return [normalized] if normalized else []

    for candidate in (cleaned, raw.replace('\\"', '"').replace("\\\\", "\\")):
        try:
            nested = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(nested, dict):
            nested_urls = extract_bilibili_miniapp_urls(nested)
            if nested_urls:
                return nested_urls
            return _urls_from_nested_payload(nested)
        if isinstance(nested, str):
            return _unwrap_qqdocurl(nested)

    normalized = normalize_bilibili_url(cleaned)
    return [normalized] if normalized and _looks_bilibili_related(normalized) else []


def _urls_from_nested_payload(payload: dict) -> list[str]:
    found: list[str] = []
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return found
    for detail in meta.values():
        if isinstance(detail, dict):
            qqdocurl = detail.get("qqdocurl")
            if isinstance(qqdocurl, str):
                found.extend(_unwrap_qqdocurl(qqdocurl))
    return found


def _urls_from_share_template(template: dict) -> list[str]:
    found: list[str] = []

    for key in ("bvid", "bvid_str", "BV", "bv_id"):
        value = template.get(key)
        if isinstance(value, str) and _BVID.fullmatch(value.strip()):
            found.append(value.strip())

    for key in ("room_id", "roomId", "live_room_id", "roomid"):
        value = template.get(key)
        if value is not None and str(value).isdigit():
            found.append(f"https://live.bilibili.com/{int(value)}")

    return found


def _looks_bilibili_related(value: str) -> bool:
    lowered = value.lower()
    return (
        "bilibili.com" in lowered
        or "b23.tv" in lowered
        or _BVID.search(value) is not None
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
