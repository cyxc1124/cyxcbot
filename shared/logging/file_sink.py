"""Persist NoneBot/loguru output to a session log file per process start."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from nonebot.log import logger as nb_logger

DEFAULT_LOG_FILE = "data/logs/cyxcbot.log"
DEFAULT_ROTATION = "10 MB"
DEFAULT_RETENTION = "7 days"
_FILE_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}"
)
_RETENTION_RE = re.compile(
    r"^(\d+)\s*(second|minute|hour|day|week)s?$",
    re.IGNORECASE,
)
_RETENTION_UNIT_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
}

_installed = False


def _env_bool(key: str, *, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "")


def resolve_log_file_path(path: str | None = None) -> Path:
    """Resolve the configured base log path; relative paths anchor to CWD."""
    raw = (path or os.getenv("LOG_FILE_PATH") or DEFAULT_LOG_FILE).strip()
    file_path = Path(raw)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    return file_path


def parse_retention(raw: str) -> timedelta:
    """Parse log retention duration (ponytail: ``N unit`` only; not full loguru grammar)."""
    match = _RETENTION_RE.match(raw.strip().lower())
    if not match:
        return timedelta(days=7)
    count = int(match.group(1))
    unit = match.group(2).lower()
    return timedelta(seconds=count * _RETENTION_UNIT_SECONDS[unit])


def build_session_log_path(
    base_path: Path,
    *,
    started_at: datetime | None = None,
) -> Path:
    """Build ``{stem}.{YYYY-MM-DD_HH-MM-SS.mmm}{suffix}`` under the same directory."""
    moment = started_at or datetime.now()
    ts = moment.strftime("%Y-%m-%d_%H-%M-%S") + f".{moment.microsecond // 1000:03d}"
    return base_path.parent / f"{base_path.stem}.{ts}{base_path.suffix}"


def _archive_legacy_active_log(base_path: Path) -> None:
    """Rename a legacy ``cyxcbot.log`` active file into a timestamped archive."""
    if not base_path.is_file():
        return
    moment = datetime.fromtimestamp(base_path.stat().st_mtime)
    ts = moment.strftime("%Y-%m-%d_%H-%M-%S") + f".{moment.microsecond // 1000:03d}"
    archived = base_path.parent / f"{base_path.stem}.archived-{ts}{base_path.suffix}"
    base_path.rename(archived)


def prune_old_session_logs(
    log_dir: Path,
    *,
    stem: str,
    suffix: str,
    retention: timedelta,
) -> int:
    """Delete archived session logs older than ``retention``; returns removed count."""
    if not log_dir.is_dir():
        return 0
    cutoff = datetime.now().timestamp() - retention.total_seconds()
    removed = 0
    for path in log_dir.glob(f"{stem}.*{suffix}"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def install_file_log_sink() -> Path | None:
    """Register a per-startup file sink on the NoneBot loguru logger (idempotent).

    Each process start writes to ``{stem}.{timestamp}{suffix}``; a legacy plain
    ``LOG_FILE_PATH`` file is renamed on first use. Within a session the active
    file rotates at ``LOG_FILE_ROTATION`` (default ``10 MB``). Old session files
    are pruned on startup according to ``LOG_FILE_RETENTION`` (default ``7 days``).
    """
    global _installed
    if _installed:
        return None
    _installed = True

    if not _env_bool("LOG_FILE_ENABLED", default=True):
        return None

    base_path = resolve_log_file_path()
    base_path.parent.mkdir(parents=True, exist_ok=True)

    retention_raw = os.getenv("LOG_FILE_RETENTION", DEFAULT_RETENTION).strip() or DEFAULT_RETENTION
    retention = parse_retention(retention_raw)

    _archive_legacy_active_log(base_path)
    removed = prune_old_session_logs(
        base_path.parent,
        stem=base_path.stem,
        suffix=base_path.suffix,
        retention=retention,
    )

    file_path = build_session_log_path(base_path)
    level = os.getenv("LOG_FILE_LEVEL") or os.getenv("LOG_LEVEL", "INFO")
    rotation = os.getenv("LOG_FILE_ROTATION", DEFAULT_ROTATION).strip() or DEFAULT_ROTATION

    nb_logger.add(
        str(file_path),
        format=_FILE_LOG_FORMAT,
        level=level.upper(),
        rotation=rotation,
        retention=retention_raw,
        encoding="utf-8",
        enqueue=True,
        catch=True,
    )
    nb_logger.info(
        "文件日志已启用: {} (level={}, rotation={}, retention={}, pruned={})",
        file_path,
        level.upper(),
        rotation,
        retention_raw,
        removed,
    )
    return file_path
