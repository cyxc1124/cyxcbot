"""Download X media (video) via the shared aiohttp session (honors proxy)."""

from __future__ import annotations

import os
from pathlib import Path

import aiohttp
from nonebot.log import logger

from .models import TweetItem, TweetMediaItem

# 对齐抖音 file:// 直读上限（QQ / NapCat 视频硬顶约 1GB）。
DEFAULT_MAX_BYTES = 1024 * 1024 * 1024
_CHUNK = 256 * 1024


async def download_url(
    session: aiohttp.ClientSession,
    url: str,
    save_path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bool:
    tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=300, sock_connect=15)
        ) as response:
            if response.status != 200:
                logger.warning(
                    "X 媒体下载失败: HTTP {} url={}", response.status, url[:120]
                )
                return False
            written = 0
            with open(tmp_path, "wb") as handle:
                async for chunk in response.content.iter_chunked(_CHUNK):
                    written += len(chunk)
                    if written > max_bytes:
                        logger.warning(
                            "X 媒体超过大小上限 {} bytes: {}",
                            max_bytes,
                            save_path.name,
                        )
                        tmp_path.unlink(missing_ok=True)
                        return False
                    handle.write(chunk)
        if written <= 0:
            tmp_path.unlink(missing_ok=True)
            return False
        os.replace(str(tmp_path), str(save_path))
        return True
    except Exception:
        logger.opt(exception=True).warning("X 媒体下载异常: {}", url[:120])
        tmp_path.unlink(missing_ok=True)
        return False


async def materialize_tweet_videos(
    session: aiohttp.ClientSession,
    tweet: TweetItem,
    media_dir: Path,
) -> list[Path]:
    """Download video/gif attachments into media_dir; set file_path on items.

    Returns local paths that should be cleaned up after send.
    """
    paths: list[Path] = []
    media_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(tweet.media_items):
        if item.kind != "video" or not item.url:
            continue
        dest = media_dir / f"x_{tweet.id}_{index}.mp4"
        ok = await download_url(session, item.url, dest)
        if not ok:
            logger.warning(
                "X 视频下载失败 tweet_id={} index={}，回退为跳过该段",
                tweet.id,
                index,
            )
            continue
        item.file_path = dest
        paths.append(dest)
    return paths


def cleanup_media_files(items: list[TweetMediaItem] | list[Path]) -> None:
    paths: list[Path] = []
    for item in items:
        if isinstance(item, Path):
            paths.append(item)
        elif item.file_path is not None:
            paths.append(item.file_path)
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.opt(exception=True).debug("清理 X 临时媒体失败: {}", path)
