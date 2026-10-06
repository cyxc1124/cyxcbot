"""Send OneBot Message via OneBot V11 or official QQ Bot."""

from __future__ import annotations

import asyncio
import base64
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger

from shared.adapter.bots import (
    is_official_qq_bot,
    iter_official_bots,
    iter_onebot_bots,
)
from shared.adapter.ids import is_numeric_qq_id
from shared.adapter.inbound import (
    event_msg_id,
    group_id_of,
    is_group_event,
    user_id_of,
)
from shared.adapter.qq_errors import note_qq_api_error
from shared.notify.at_all import DYNAMIC_AT_ALL_FALLBACK, resolve_at_all_prefix

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_OFFICIAL_MIN_INTERVAL = 3.0
_official_locks: dict[str, asyncio.Lock] = {}
_official_last_sent: dict[str, float] = {}


def _official_lock(target_id: str) -> asyncio.Lock:
    lock = _official_locks.get(target_id)
    if lock is None:
        lock = asyncio.Lock()
        _official_locks[target_id] = lock
    return lock


def _is_url_forbidden(exc: BaseException) -> bool:
    text = str(exc)
    return "40054010" in text or "不允许发送URL" in text


def _is_rate_limited(exc: BaseException) -> bool:
    return "40034100" in str(exc)


def strip_urls(text: str) -> str:
    cleaned = _URL_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def truncate_text(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def convert_onebot_message(message: Message) -> list[tuple[str, Any]]:
    """Flatten OneBot Message into official send parts. Drops @all."""
    parts: list[tuple[str, Any]] = []
    text_buf: list[str] = []

    def flush_text() -> None:
        if not text_buf:
            return
        blob = "".join(text_buf)
        if blob.strip():
            parts.append(("text", blob))
        text_buf.clear()

    for seg in message:
        kind = getattr(seg, "type", "")
        data = getattr(seg, "data", {}) or {}
        if kind == "text":
            text_buf.append(str(data.get("text", "")))
            continue
        if kind == "at":
            qq = str(data.get("qq", ""))
            if qq == "all":
                continue
            text_buf.append(f"@{qq}")
            continue
        if kind in {"image", "video"}:
            flush_text()
            file_val = data.get("file") or data.get("url") or data.get("path")
            raw = getattr(seg, "data", {})
            # bytes images land as file=... or we stored them via MessageSegment.image(bytes)
            content = raw.get("file")
            parts.append((kind, content if content is not None else file_val))
            continue
        if kind == "file":
            flush_text()
            parts.append(("file", data.get("file") or data.get("path")))
    flush_text()
    return parts


async def _materialize_media(value: Any) -> bytes | Path | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, Path):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("base64://"):
        return base64.b64decode(text.removeprefix("base64://"), validate=True)
    if text.startswith("file://"):
        parsed = urlparse(text)
        return Path(unquote(parsed.path))
    if text.startswith("http://") or text.startswith("https://"):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(text)
            resp.raise_for_status()
            return resp.content
    path = Path(text)
    if path.exists():
        return path
    return None


async def _to_official_segment(kind: str, value: Any):
    from nonebot.adapters.qq import MessageSegment

    if kind == "text":
        return MessageSegment.text(truncate_text(str(value)))
    media = await _materialize_media(value)
    if media is None:
        raise ValueError("官方 Bot 媒体内容为空或文件不存在")
    if isinstance(media, Path):
        data: bytes | Path = media
        name = media.name
    else:
        data = media
        name = "image.jpg" if kind == "image" else "video.mp4"
    if kind == "video":
        return MessageSegment.file_video(data, file_name=name)
    return MessageSegment.file_image(data, file_name=name)


async def _send_official_once(
    bot: Any,
    *,
    event: Any | None,
    group_id: str | None,
    user_id: str | None,
    kind: str,
    value: Any,
    msg_seq: int,
) -> None:
    from nonebot.adapters.qq import Message

    segment = await _to_official_segment(kind, value)
    payload = Message(segment)
    if event is not None:
        # QQ 适配器在事件上递增 _reply_seq，跨批次和 Matcher 共用回复序号。
        await bot.send(event, payload)
        return
    if group_id:
        await bot.send_to_group(group_openid=group_id, message=payload, msg_seq=msg_seq)
        return
    await bot.send_to_c2c(openid=str(user_id), message=payload, msg_seq=msg_seq)


async def _send_official_parts(
    bot: Any,
    parts: list[tuple[str, Any]],
    *,
    event: Any | None = None,
    group_id: str | None = None,
    user_id: str | None = None,
) -> None:
    if event is not None:
        if not event_msg_id(event):
            raise ValueError("官方 Bot 被动回复缺少消息 ID")
        target = group_id_of(event) if is_group_event(event) else user_id_of(event)
    else:
        target = group_id or user_id
    if not target:
        raise ValueError("官方 Bot 发送目标为空")
    seq = 1
    async with _official_lock(target):
        for kind, value in parts:
            now = time.monotonic()
            last = _official_last_sent.get(target, 0.0)
            wait = _OFFICIAL_MIN_INTERVAL - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            retries = 0
            send_value = value
            while True:
                try:
                    await _send_official_once(
                        bot,
                        event=event,
                        group_id=group_id,
                        user_id=user_id,
                        kind=kind,
                        value=send_value,
                        msg_seq=seq,
                    )
                    break
                except Exception as exc:
                    if (
                        kind == "text"
                        and _is_url_forbidden(exc)
                        and send_value == value
                    ):
                        stripped = strip_urls(str(value)) or "（链接已省略）"
                        if stripped != send_value:
                            logger.warning("官方 Bot 拒绝 URL，去掉链接后重试")
                            send_value = stripped
                            continue
                    if _is_rate_limited(exc) and retries < 2:
                        retries += 1
                        await asyncio.sleep(3 * retries)
                        continue
                    noted = note_qq_api_error(exc, target=str(target))
                    if noted is not None:
                        raise noted from None
                    raise
            seq += 1
            _official_last_sent[target] = time.monotonic()


async def send_group(
    group_id: str,
    message: Message,
    *,
    at_all: bool = False,
    at_all_fallback: str = DYNAMIC_AT_ALL_FALLBACK,
) -> None:
    gid = str(group_id).strip()
    if not gid:
        raise RuntimeError("群 ID 为空")
    if is_numeric_qq_id(gid):
        bots = iter_onebot_bots()
        if not bots:
            raise RuntimeError("没有可用的机器人实例")
        last_exc: Exception | None = None
        for bot in bots:
            try:
                payload = message
                if at_all:
                    prefix = await resolve_at_all_prefix(
                        bot,
                        gid,
                        enabled=True,
                        fallback=at_all_fallback,
                    )
                    payload = prefix + message
                await bot.send_group_msg(group_id=int(gid), message=payload)
                return
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("发送群消息失败")

    bots = iter_official_bots()
    if not bots:
        raise RuntimeError("没有可用的官方机器人实例")
    parts = convert_onebot_message(message)
    if at_all:
        parts = [("text", at_all_fallback), *parts]
    if not parts:
        return
    last_exc = None
    for bot in bots:
        try:
            await _send_official_parts(bot, parts, group_id=gid)
            return
        except Exception as exc:
            last_exc = exc
    raise last_exc or RuntimeError("发送官方群消息失败")


async def send_user(user_id: str, message: Message) -> None:
    uid = str(user_id).strip()
    if not uid:
        raise RuntimeError("用户 ID 为空")
    if is_numeric_qq_id(uid):
        bots = iter_onebot_bots()
        if not bots:
            raise RuntimeError("没有可用的机器人实例")
        last_exc: Exception | None = None
        for bot in bots:
            try:
                await bot.send_private_msg(user_id=int(uid), message=message)
                return
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("发送私聊失败")

    bots = iter_official_bots()
    if not bots:
        raise RuntimeError("没有可用的官方机器人实例")
    parts = convert_onebot_message(message)
    if not parts:
        return
    last_exc = None
    for bot in bots:
        try:
            await _send_official_parts(bot, parts, user_id=uid)
            return
        except Exception as exc:
            last_exc = exc
    raise last_exc or RuntimeError("发送官方私聊失败")


async def send_event_message(bot: Any, event: Any, message: Message) -> Any:
    """Reply on the event's adapter. Official path converts OneBot Message."""
    if is_official_qq_bot(bot):
        parts = convert_onebot_message(message)
        if not parts:
            return None
        await _send_official_parts(bot, parts, event=event)
        return {"ok": True}
    if is_group_event(event):
        gid = group_id_of(event)
        return await bot.send_group_msg(
            group_id=int(gid) if gid else 0, message=message
        )
    uid = user_id_of(event)
    return await bot.send_private_msg(user_id=int(uid) if uid else 0, message=message)


async def send_event_text(bot: Any, event: Any, text: str) -> Any:
    if is_official_qq_bot(bot):
        return await send_event_message(bot, event, Message(text))
    return await bot.send(event, text)
