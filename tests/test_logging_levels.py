"""Runtime log thresholds must not couple terminal, file and Web output."""

from typing import get_args

import pytest
from nonebot.log import default_filter, logger

from shared.config.types import AppConfigSnapshot
from shared.logging import levels


@pytest.mark.parametrize(
    ("terminal", "file"),
    [("ERROR", "TRACE"), ("TRACE", "WARNING"), ("CRITICAL", "ERROR")],
)
@pytest.mark.asyncio
async def test_hot_reload_keeps_outputs_independent(terminal, file, monkeypatch):
    previous_extra = dict(logger._core.extra)
    monkeypatch.setattr(levels, "_file_level_no", levels._file_level_no)
    outputs = {"terminal": [], "file": [], "web": []}
    handlers = [
        logger.add(outputs["terminal"].append, level=0, filter=default_filter),
        logger.add(outputs["file"].append, level=0, filter=levels.file_log_filter),
        logger.add(outputs["web"].append, level="DEBUG"),
    ]
    try:
        await levels.on_config_reload(
            AppConfigSnapshot(log_level=terminal, log_file_level=file)
        )
        for level in get_args(levels.LogLevel):
            logger.log(level, "threshold probe")

        for output, threshold in (
            ("terminal", terminal),
            ("file", file),
            ("web", "DEBUG"),
        ):
            actual = [message.record["level"].name for message in outputs[output]]
            expected = [
                level
                for level in get_args(levels.LogLevel)
                if logger.level(level).no >= logger.level(threshold).no
            ]
            assert actual == expected
    finally:
        for handler in handlers:
            logger.remove(handler)
        logger.configure(extra=previous_extra)


@pytest.mark.parametrize(
    ("terminal", "file", "expected"),
    [
        ("DEBUG", "ERROR", ("DEBUG", "ERROR")),
        ("WARNING", "", ("WARNING", "WARNING")),
        ("invalid", "debug", ("INFO", "DEBUG")),
        (" warning ", "", ("WARNING", "WARNING")),
    ],
)
def test_environment_defaults(terminal, file, expected, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", terminal)
    monkeypatch.setenv("LOG_FILE_LEVEL", file)
    assert levels.default_log_levels() == expected
