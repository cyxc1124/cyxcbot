"""Independent, hot-reloadable terminal and file log thresholds."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal, cast, get_args

from nonebot.log import logger

if TYPE_CHECKING:
    from loguru import Record

    from shared.config.types import AppConfigSnapshot

LogLevel = Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]

_file_level_no = 20


def normalize_log_level(value: str, default: LogLevel = "INFO") -> LogLevel:
    level = value.strip().upper()
    return cast(LogLevel, level) if level in get_args(LogLevel) else default


def default_log_levels() -> tuple[LogLevel, LogLevel]:
    terminal = normalize_log_level(os.getenv("LOG_LEVEL", "INFO"))
    file = normalize_log_level(os.getenv("LOG_FILE_LEVEL", ""), terminal)
    return terminal, file


def set_file_log_level(level: LogLevel) -> None:
    global _file_level_no
    _file_level_no = logger.level(level).no


def file_log_filter(record: Record) -> bool:
    return record["level"].no >= _file_level_no


async def on_config_reload(snapshot: AppConfigSnapshot) -> None:
    set_file_log_level(snapshot.log_file_level)
    # NoneBot's stdout filter reads this extra; Web and file sinks ignore it.
    logger.configure(extra={"nonebot_log_level": snapshot.log_level})
