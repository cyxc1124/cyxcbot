"""Tests for rotating file log sink."""

from __future__ import annotations

from pathlib import Path

import pytest

import shared.logging.file_sink as file_sink
from shared.logging.file_sink import install_file_log_sink, resolve_log_file_path


def test_resolve_log_file_path_relative() -> None:
    path = resolve_log_file_path("data/logs/test.log")
    assert path == Path.cwd() / "data/logs/test.log"


def test_install_file_log_sink_writes_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_file = tmp_path / "logs" / "cyxcbot.log"
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    monkeypatch.setenv("LOG_FILE_LEVEL", "INFO")
    file_sink._installed = False

    result = install_file_log_sink()
    assert result == log_file
    assert log_file.is_file()
    assert "文件日志已启用" in log_file.read_text(encoding="utf-8")


def test_install_file_log_sink_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FILE_ENABLED", "false")
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "unused.log"))
    file_sink._installed = False

    assert install_file_log_sink() is None
    assert not (tmp_path / "unused.log").exists()
