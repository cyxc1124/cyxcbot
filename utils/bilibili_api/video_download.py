"""B 站视频下载：WBI playurl → DASH 分轨 → FFmpeg 混流（对齐 DownKyi / bili_download.py）。"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

import aiohttp
from nonebot.log import logger

from utils.douyin_api.download import download_file

from . import wbi

REFERER = "https://www.bilibili.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FNVAL_DASH = 4048
# 默认取 720P：群聊观感够用；体积上限对齐协议端原始文件硬顶（file:// 直读，无 base64）。
DEFAULT_PREFER_QN = 64
# LuckyLilliaBot ``SendElement.video`` 硬顶为原始文件 1024MB（entities.ts）。
DEFAULT_MAX_BYTES = 1024 * 1024 * 1024


class BilibiliVideoDownloadError(Exception):
    """视频下载失败（可降级为仅封面+文字）。"""


def _stream_urls(stream: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    base = stream.get("baseUrl") or stream.get("base_url")
    if base:
        urls.append(base)
    urls.extend(stream.get("backupUrl") or stream.get("backup_url") or [])
    return urls


def select_dash_streams(
    play: dict[str, Any], prefer_qn: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """选择最佳 DASH 音视频轨（同画质优先 H.264；不超过 prefer 时取最高，否则取最低）。"""
    dash = play.get("dash")
    if not dash:
        raise BilibiliVideoDownloadError("当前视频无 DASH 流")

    videos = dash.get("video") or []
    audios = dash.get("audio") or []
    if not videos or not audios:
        raise BilibiliVideoDownloadError("DASH 缺少 video 或 audio 轨")

    capped = [v for v in videos if int(v.get("id") or 0) <= prefer_qn]
    if capped:
        best_qn = max(int(v.get("id") or 0) for v in capped)
        same_qn = [v for v in capped if int(v.get("id") or 0) == best_qn]
    else:
        # 全部高于 prefer：取最低档，避免抬到更高清撑爆体积
        best_qn = min(int(v.get("id") or 0) for v in videos)
        same_qn = [v for v in videos if int(v.get("id") or 0) == best_qn]
    same_qn.sort(
        key=lambda v: 0 if v.get("codecid") == 7 else 1 if v.get("codecid") == 12 else 2
    )
    video = same_qn[0]

    eligible_audio = [a for a in audios if int(a.get("id") or 0) <= 30280] or audios
    audio = max(eligible_audio, key=lambda a: int(a.get("id") or 0))
    return video, audio


def pick_request_qn(accept_quality: list[int] | None, prefer_qn: int) -> int:
    if not accept_quality:
        return prefer_qn
    reachable = [q for q in accept_quality if q <= prefer_qn]
    if reachable:
        return max(reachable)
    # 没有 ≤ prefer 的档位时取最低可用，避免请求更高清
    return min(accept_quality)


async def fetch_playurl(
    session: aiohttp.ClientSession,
    *,
    bvid: str,
    cid: int,
    cookie: Optional[str],
    qn: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "fourk": 1,
        "fnver": 0,
        "fnval": FNVAL_DASH,
        "cid": cid,
        "qn": qn,
        "bvid": bvid,
    }
    signed = await wbi.sign_params(session, params, cookie)
    if not signed:
        raise BilibiliVideoDownloadError("WBI 签名失败，无法获取播放地址")

    url = f"https://api.bilibili.com/x/player/wbi/playurl?{signed}"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Accept": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie

    async with session.get(url, headers=headers, timeout=20) as resp:
        if resp.status != 200:
            raise BilibiliVideoDownloadError(f"playurl HTTP {resp.status}")
        payload = await resp.json()

    if payload.get("code") != 0:
        raise BilibiliVideoDownloadError(
            f"playurl 失败: {payload.get('message', '未知错误')}"
        )
    play = payload.get("data") or payload.get("result")
    if not play:
        raise BilibiliVideoDownloadError("playurl 响应为空")
    return play


async def _download_cdn(
    session: aiohttp.ClientSession,
    urls: list[str],
    dest: Path,
    *,
    cookie: Optional[str],
    max_bytes: int,
    label: str,
) -> None:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
    }
    if cookie:
        headers["Cookie"] = cookie

    last_err: Exception | None = None
    for i, url in enumerate(urls):
        try:
            ok = await download_file(
                url,
                dest,
                session,
                headers=headers,
                max_bytes=max_bytes,
            )
            if ok and dest.exists() and dest.stat().st_size > 0:
                logger.info(
                    "B 站{}下载完成: {} ({:.2f} MB)",
                    label,
                    dest.name,
                    dest.stat().st_size / 1024 / 1024,
                )
                return
            last_err = BilibiliVideoDownloadError(f"{label} CDN[{i}] 下载失败")
        except Exception as exc:
            last_err = exc
            logger.warning("B 站{} CDN[{}] 失败: {}", label, i, exc)
    raise BilibiliVideoDownloadError(f"{label} 全部 CDN 均失败") from last_err


async def _merge_av(audio: Path, video: Path, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise BilibiliVideoDownloadError("未找到 ffmpeg，无法混流")

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio),
        "-i",
        str(video),
        "-c",
        "copy",
        "-strict",
        "-2",
        "-movflags",
        "+faststart",
        str(output),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = (stderr or b"").decode("utf-8", errors="replace")[:300]
        raise BilibiliVideoDownloadError(f"FFmpeg 混流失败: {detail}")


async def _try_durl(
    session: aiohttp.ClientSession,
    play: dict[str, Any],
    dest: Path,
    *,
    cookie: Optional[str],
    max_bytes: int,
) -> Path | None:
    durl = play.get("durl") or []
    if not durl:
        return None
    url = durl[0].get("url")
    if not url:
        return None
    await _download_cdn(
        session,
        [url],
        dest,
        cookie=cookie,
        max_bytes=max_bytes,
        label="整段流",
    )
    return dest


def _cleanup_work_dir(work: Path, *, owned: bool) -> None:
    if not owned:
        return
    try:
        shutil.rmtree(work, ignore_errors=True)
    except Exception:
        logger.opt(exception=True).debug("清理 B 站下载临时目录失败: {}", work)


async def download_bilibili_video(
    session: aiohttp.ClientSession,
    *,
    bvid: str,
    cid: int,
    cookie: Optional[str] = None,
    prefer_qn: int = DEFAULT_PREFER_QN,
    max_bytes: int = DEFAULT_MAX_BYTES,
    output_dir: Path | None = None,
) -> Path:
    """下载单 P 视频为本地 mp4，调用方负责清理返回的文件路径。

    ``max_bytes`` 默认对齐 LuckyLilliaBot 视频硬顶（1024MB 原始文件）。
    超限时抛错，由链接解析降级为封面+文字。
    ``output_dir`` 为空时使用系统临时目录；失败会清理该临时目录。
    ``output_dir`` 非空时写入共享目录（不删目录本身），失败仅删除产物文件。
    """
    if not bvid or not cid:
        raise BilibiliVideoDownloadError("缺少 bvid 或 cid")

    owned_work = output_dir is None
    work = (
        Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="bilibili_"))
    )
    work.mkdir(parents=True, exist_ok=True)
    stem = f"{bvid}_{cid}_{uuid.uuid4().hex[:8]}"
    final = work / f"{stem}.mp4"

    try:
        return await _download_bilibili_video_into(
            session,
            work=work,
            final=final,
            stem=stem,
            bvid=bvid,
            cid=cid,
            cookie=cookie,
            prefer_qn=prefer_qn,
            max_bytes=max_bytes,
        )
    except Exception:
        final.unlink(missing_ok=True)
        _cleanup_work_dir(work, owned=owned_work)
        raise


async def _download_bilibili_video_into(
    session: aiohttp.ClientSession,
    *,
    work: Path,
    final: Path,
    stem: str,
    bvid: str,
    cid: int,
    cookie: Optional[str],
    prefer_qn: int,
    max_bytes: int,
) -> Path:
    probe = await fetch_playurl(
        session, bvid=bvid, cid=cid, cookie=cookie, qn=prefer_qn
    )
    request_qn = pick_request_qn(probe.get("accept_quality"), prefer_qn)
    play = (
        probe
        if request_qn == prefer_qn
        else await fetch_playurl(
            session, bvid=bvid, cid=cid, cookie=cookie, qn=request_qn
        )
    )

    try:
        video_stream, audio_stream = select_dash_streams(play, request_qn)
    except BilibiliVideoDownloadError as dash_err:
        # DASH 不可用时尝试 durl 整段（无需 ffmpeg）
        try:
            durl_path = await _try_durl(
                session, play, final, cookie=cookie, max_bytes=max_bytes
            )
            if durl_path is not None:
                if durl_path.stat().st_size > max_bytes:
                    durl_path.unlink(missing_ok=True)
                    raise BilibiliVideoDownloadError("视频超过发送大小上限")
                return durl_path
        except BilibiliVideoDownloadError:
            pass
        raise dash_err

    if not shutil.which("ffmpeg"):
        try:
            durl_path = await _try_durl(
                session, play, final, cookie=cookie, max_bytes=max_bytes
            )
            if durl_path is not None:
                if durl_path.stat().st_size > max_bytes:
                    durl_path.unlink(missing_ok=True)
                    raise BilibiliVideoDownloadError("视频超过发送大小上限")
                return durl_path
        except BilibiliVideoDownloadError:
            pass
        raise BilibiliVideoDownloadError("未找到 ffmpeg，且无可用整段流")

    tmp_video = work / f"{stem}.video.m4s"
    tmp_audio = work / f"{stem}.audio.m4s"
    try:
        await _download_cdn(
            session,
            _stream_urls(video_stream),
            tmp_video,
            cookie=cookie,
            max_bytes=max_bytes,
            label="视频轨",
        )
        await _download_cdn(
            session,
            _stream_urls(audio_stream),
            tmp_audio,
            cookie=cookie,
            max_bytes=max_bytes,
            label="音频轨",
        )
        await _merge_av(tmp_audio, tmp_video, final)
        if not final.exists() or final.stat().st_size <= 0:
            raise BilibiliVideoDownloadError("混流产物为空")
        if final.stat().st_size > max_bytes:
            final.unlink(missing_ok=True)
            raise BilibiliVideoDownloadError("视频超过发送大小上限")
        logger.info(
            "B 站视频就绪: bvid={} cid={} qn={} size={:.2f}MB",
            bvid,
            cid,
            video_stream.get("id"),
            final.stat().st_size / 1024 / 1024,
        )
        return final
    finally:
        for path in (tmp_video, tmp_audio):
            path.unlink(missing_ok=True)
