"""Stream download with aiohttp + httpx 403 fallback (from FileManager)."""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

import aiohttp
import httpx
from nonebot.log import logger

_DOWNLOAD_CHUNK_BYTES = 256 * 1024
_DOWNLOAD_TOTAL_TIMEOUT_S = 300
_DOWNLOAD_CONNECT_TIMEOUT_S = 15
_DOWNLOAD_READ_STALL_TIMEOUT_S = 60

# QQ 群发视频合理上限；超出视为失败并清理
DEFAULT_MAX_BYTES = 80 * 1024 * 1024


def _complete_content_range_size(response_headers) -> Optional[int]:
    if not response_headers:
        return None
    content_range = response_headers.get("Content-Range")
    if not content_range:
        return None
    match = re.match(r"^bytes (\d+)-(\d+)/(\d+)$", content_range.strip())
    if not match:
        return None
    start, end, total = (int(part) for part in match.groups())
    if start != 0 or end + 1 != total:
        return None
    return total


async def _persist_stream(
    chunk_iter: AsyncIterator[bytes],
    save_path: Path,
    expected_size: Optional[int],
    *,
    max_bytes: int,
) -> bool:
    tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")
    written = 0
    try:
        with open(tmp_path, "wb") as f:
            async for chunk in chunk_iter:
                written += len(chunk)
                if written > max_bytes:
                    logger.warning(
                        "下载超过大小上限 {} bytes，中止: {}",
                        max_bytes,
                        save_path.name,
                    )
                    tmp_path.unlink(missing_ok=True)
                    return False
                f.write(chunk)
        if expected_size is not None and written != expected_size:
            logger.warning(
                "大小不匹配 {}: expected={}, got={}",
                save_path.name,
                expected_size,
                written,
            )
            tmp_path.unlink(missing_ok=True)
            return False
        os.replace(str(tmp_path), str(save_path))
        return True
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


async def _download_via_httpx(
    url: str,
    save_path: Path,
    *,
    headers: Optional[dict[str, str]] = None,
    proxy: Optional[str] = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bool:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                _DOWNLOAD_TOTAL_TIMEOUT_S,
                connect=_DOWNLOAD_CONNECT_TIMEOUT_S,
                read=_DOWNLOAD_READ_STALL_TIMEOUT_S,
            ),
            proxy=proxy or None,
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    logger.debug(
                        "httpx 回退失败 {}: status={}",
                        save_path.name,
                        response.status_code,
                    )
                    return False
                expected_size: Optional[int] = None
                if not response.headers.get("Content-Encoding"):
                    content_length = response.headers.get("Content-Length")
                    if content_length is not None and content_length.isdigit():
                        expected_size = int(content_length)
                        if expected_size > max_bytes:
                            logger.warning(
                                "Content-Length {} 超过上限 {}",
                                expected_size,
                                max_bytes,
                            )
                            return False
                return await _persist_stream(
                    response.aiter_bytes(),
                    save_path,
                    expected_size,
                    max_bytes=max_bytes,
                )
    except Exception as exc:
        logger.debug("httpx 回退异常 {}: {}", save_path.name, exc)
        return False


async def download_file(
    url: str,
    save_path: Path,
    session: aiohttp.ClientSession,
    *,
    headers: Optional[dict[str, str]] = None,
    proxy: Optional[str] = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bool:
    """Download ``url`` to ``save_path``; on HTTP 403 retry via httpx."""
    tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(
                total=_DOWNLOAD_TOTAL_TIMEOUT_S,
                connect=_DOWNLOAD_CONNECT_TIMEOUT_S,
                sock_read=_DOWNLOAD_READ_STALL_TIMEOUT_S,
            ),
            headers=headers,
            proxy=proxy or None,
        ) as response:
            if response.status == 200:
                if (
                    response.content_length is not None
                    and response.content_length > max_bytes
                ):
                    logger.warning(
                        "Content-Length {} 超过上限 {}",
                        response.content_length,
                        max_bytes,
                    )
                    return False
                return await _persist_stream(
                    response.content.iter_chunked(_DOWNLOAD_CHUNK_BYTES),
                    save_path,
                    response.content_length,
                    max_bytes=max_bytes,
                )
            if response.status == 206:
                expected_size = _complete_content_range_size(response.headers)
                if expected_size is None:
                    logger.warning(
                        "拒绝不完整 Range 响应 {}: {}",
                        save_path.name,
                        response.headers.get("Content-Range")
                        if response.headers
                        else None,
                    )
                    return False
                if expected_size > max_bytes:
                    return False
                return await _persist_stream(
                    response.content.iter_chunked(_DOWNLOAD_CHUNK_BYTES),
                    save_path,
                    expected_size,
                    max_bytes=max_bytes,
                )
            status = response.status
            logger.debug("下载失败 {}: status={}", save_path.name, status)
        if status == 403:
            return await _download_via_httpx(
                url,
                save_path,
                headers=headers,
                proxy=proxy,
                max_bytes=max_bytes,
            )
        return False
    except Exception as exc:
        logger.debug("下载异常 {}: {}", save_path.name, exc)
        tmp_path.unlink(missing_ok=True)
        return False
