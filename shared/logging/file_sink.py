"""Persist NoneBot/loguru output to a rotating log file."""

from __future__ import annotations

import os
from pathlib import Path

from nonebot.log import logger as nb_logger

DEFAULT_LOG_FILE = "data/logs/cyxcbot.log"
DEFAULT_ROTATION = "10 MB"
DEFAULT_RETENTION = "7 days"
_FILE_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}"
)

_installed = False


def _env_bool(key: str, *, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "")


def resolve_log_file_path(path: str | None = None) -> Path:
    """Resolve log file path; relative paths are anchored to CWD."""
    raw = (path or os.getenv("LOG_FILE_PATH") or DEFAULT_LOG_FILE).strip()
    file_path = Path(raw)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    return file_path


def install_file_log_sink() -> Path | None:
    """Register a rotating file sink on the NoneBot loguru logger (idempotent).

    Controlled by ``LOG_FILE_ENABLED`` (default true), ``LOG_FILE_PATH``,
    ``LOG_FILE_LEVEL`` (defaults to ``LOG_LEVEL``), ``LOG_FILE_ROTATION``,
    and ``LOG_FILE_RETENTION``.
    """
    global _installed
    if _installed:
        return None
    _installed = True

    if not _env_bool("LOG_FILE_ENABLED", default=True):
        return None

    file_path = resolve_log_file_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    level = os.getenv("LOG_FILE_LEVEL") or os.getenv("LOG_LEVEL", "INFO")
    rotation = os.getenv("LOG_FILE_ROTATION", DEFAULT_ROTATION).strip() or DEFAULT_ROTATION
    retention = os.getenv("LOG_FILE_RETENTION", DEFAULT_RETENTION).strip() or DEFAULT_RETENTION

    nb_logger.add(
        str(file_path),
        format=_FILE_LOG_FORMAT,
        level=level.upper(),
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
        catch=True,
    )
    nb_logger.info(
        "文件日志已启用: {} (level={}, rotation={}, retention={})",
        file_path,
        level.upper(),
        rotation,
        retention,
    )
    return file_path
