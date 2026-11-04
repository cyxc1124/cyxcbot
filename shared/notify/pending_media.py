"""把待投递消息里的 base64 媒体存成文件，数据库只保留短引用。

截图/卡片是 base64 内联在消息段里的，每次 ``_persist_state`` 都会随 JSON 整行重写
（一条动态要写多次），体积可达数 MB。这里按内容哈希落盘，同一张图只写一次。
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any

from nonebot.log import logger

PENDING_MEDIA_DIR = Path("data") / "pending_media"

_BASE64_PREFIX = "base64://"
_REF_PREFIX = "pending-media://"
_REF_RE = re.compile(r"^[0-9a-f]{64}$")
# 小于该长度的内联内容留在 JSON 里，不值得落盘。
_MIN_EXTERNAL_CHARS = 4096
# 需大于 PENDING_DELIVERY_MAX_AGE_SECONDS（6h），且每次持久化都会刷新 mtime。
_PRUNE_AGE_SECONDS = 12 * 3600
_PRUNE_INTERVAL_SECONDS = 600
_last_prune = 0.0


def _path_for(digest: str) -> Path:
    return PENDING_MEDIA_DIR / digest


def _prune_if_due(now: float) -> None:
    global _last_prune
    if now - _last_prune < _PRUNE_INTERVAL_SECONDS:
        return
    _last_prune = now
    try:
        for path in PENDING_MEDIA_DIR.iterdir():
            if (
                _REF_RE.match(path.name)
                and now - path.stat().st_mtime > _PRUNE_AGE_SECONDS
            ):
                path.unlink(missing_ok=True)
    except OSError:
        logger.opt(exception=True).warning("清理待投递媒体文件失败")


def externalize_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回副本：大块 base64 文件换成 ``pending-media://<sha256>``。"""
    result: list[dict[str, Any]] = []
    now = time.time()
    for segment in segments:
        data = segment.get("data") or {}
        file = data.get("file")
        if (
            isinstance(file, str)
            and file.startswith(_BASE64_PREFIX)
            and len(file) >= _MIN_EXTERNAL_CHARS
        ):
            try:
                raw = b64decode(file[len(_BASE64_PREFIX) :], validate=True)
                digest = hashlib.sha256(raw).hexdigest()
                path = _path_for(digest)
                if path.exists():
                    os.utime(path)
                else:
                    PENDING_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".tmp")
                    tmp.write_bytes(raw)
                    os.replace(tmp, path)
                segment = {
                    **segment,
                    "data": {**data, "file": f"{_REF_PREFIX}{digest}"},
                }
            except OSError, ValueError:
                # 落盘失败时退回内联，宁可大一点也不能丢消息。
                logger.opt(exception=True).warning("待投递媒体落盘失败，保留内联")
        result.append(segment)
    _prune_if_due(now)
    return result


def inline_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """还原 :func:`externalize_segments`；文件缺失的媒体段被丢弃。"""
    result: list[dict[str, Any]] = []
    for segment in segments:
        data = segment.get("data") or {}
        file = data.get("file")
        if isinstance(file, str) and file.startswith(_REF_PREFIX):
            digest = file[len(_REF_PREFIX) :]
            try:
                if not _REF_RE.match(digest):
                    raise ValueError("无效的媒体引用")
                raw = _path_for(digest).read_bytes()
            except OSError, ValueError:
                logger.warning("待投递媒体文件缺失，已省略该媒体段: {}", digest[:12])
                continue
            segment = {
                **segment,
                "data": {**data, "file": _BASE64_PREFIX + b64encode(raw).decode()},
            }
        result.append(segment)
    return result
