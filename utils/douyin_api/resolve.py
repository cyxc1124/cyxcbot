"""Public orchestration: share text → detail → download video file."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from nonebot.log import logger

from .client import DouyinAPIClient, LoginRequiredError
from .cookies import cookies_from_header, validate_cookies
from .download import DEFAULT_MAX_BYTES, download_file
from .url_parser import parse_video_url
from .validators import extract_douyin_urls, is_short_url, normalize_short_url
from .video_urls import build_video_url_candidates


@dataclass
class DouyinVideoResult:
    aweme_id: str
    title: str
    author: str
    share_url: str
    file_path: Path
    detail: dict[str, Any]


class DouyinResolveError(Exception):
    """Raised when a share link cannot be resolved/downloaded."""


def _author_name(detail: dict[str, Any]) -> str:
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    return str(
        author.get("nickname")
        or author.get("unique_id")
        or author.get("short_id")
        or ""
    ).strip()


def _title(detail: dict[str, Any]) -> str:
    desc = str(detail.get("desc") or "").strip()
    return desc or f"抖音视频 {detail.get('aweme_id') or ''}".strip()


def _share_url(detail: dict[str, Any], fallback: str) -> str:
    share = (
        detail.get("share_info") if isinstance(detail.get("share_info"), dict) else {}
    )
    url = str(share.get("share_url") or "").strip()
    if url:
        return url
    aweme_id = str(detail.get("aweme_id") or "").strip()
    if aweme_id:
        return f"https://www.douyin.com/video/{aweme_id}"
    return fallback


async def resolve_and_download(
    share_text: str,
    cookie_header: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    tmp_dir: Optional[Path] = None,
) -> DouyinVideoResult:
    """Resolve the first Douyin URL in ``share_text`` and download its video.

    Cookie 对齐 douyin-downloader：缺省或字段不全只 warning，仍尝试请求；
    真正失败由短链/详情/下载结果决定（如 LoginRequiredError）。
    """
    cookies = cookies_from_header(cookie_header)
    if not validate_cookies(cookies):
        logger.warning(
            "抖音 Cookie 未配置或不完整，将继续尝试解析（建议配置 ttwid/odin_tt/passport_csrf_token）"
        )

    urls = extract_douyin_urls(share_text)
    if not urls:
        raise DouyinResolveError("未识别到抖音链接")

    async with DouyinAPIClient(cookies) as client:
        resolved_url = urls[0]
        if is_short_url(resolved_url):
            final = await client.resolve_short_url(normalize_short_url(resolved_url))
            if not final:
                raise DouyinResolveError("短链解析失败")
            resolved_url = final

        parsed = parse_video_url(resolved_url)
        if not parsed or not parsed.get("aweme_id"):
            raise DouyinResolveError("无法从链接提取作品 ID")

        aweme_id = str(parsed["aweme_id"])
        try:
            detail = await client.get_video_detail(aweme_id)
        except LoginRequiredError as exc:
            raise DouyinResolveError("抖音登录已失效，请更新 Cookie") from exc
        if not detail:
            raise DouyinResolveError("获取作品详情失败")

        candidates = build_video_url_candidates(client, detail)
        if not candidates:
            raise DouyinResolveError("未找到可下载的视频地址")

        # 自建临时目录时，失败路径必须清理：插件侧 finally 仅在拿到 result 后清理，
        # 全部候选下载失败会抛 DouyinResolveError，否则 douyin_* 目录会永久泄漏占盘。
        owned_temp = tmp_dir is None
        work_dir = (
            Path(tmp_dir) if tmp_dir else Path(tempfile.mkdtemp(prefix="douyin_"))
        )
        work_dir.mkdir(parents=True, exist_ok=True)
        save_path = work_dir / f"{aweme_id}.mp4"
        try:
            session = await client.get_session()

            for url, headers in candidates:
                ok = await download_file(
                    url,
                    save_path,
                    session,
                    headers=headers,
                    max_bytes=max_bytes,
                )
                if ok and save_path.exists() and save_path.stat().st_size > 0:
                    logger.info(
                        "抖音视频已下载 aweme_id={} size={}",
                        aweme_id,
                        save_path.stat().st_size,
                    )
                    owned_temp = False  # 交由调用方（插件 finally）清理
                    return DouyinVideoResult(
                        aweme_id=aweme_id,
                        title=_title(detail),
                        author=_author_name(detail),
                        share_url=_share_url(detail, resolved_url),
                        file_path=save_path,
                        detail=detail,
                    )

            raise DouyinResolveError("视频下载失败（全部候选地址不可用）")
        finally:
            if owned_temp:
                shutil.rmtree(work_dir, ignore_errors=True)
