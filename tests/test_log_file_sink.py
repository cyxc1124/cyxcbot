"""Tests for per-startup file log sink."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

import shared.logging.file_sink as file_sink
from shared.logging.file_sink import (
    _archive_legacy_active_log,
    build_session_log_path,
    install_file_log_sink,
    managed_log_name_pattern,
    parse_retention,
    prune_old_session_logs,
    resolve_log_file_path,
)


def test_resolve_log_file_path_relative() -> None:
    path = resolve_log_file_path("data/logs/test.log")
    assert path == Path.cwd() / "data/logs/test.log"


def test_build_session_log_path() -> None:
    base = Path("data/logs/cyxcbot.log")
    started = datetime(2026, 6, 26, 14, 30, 52, 123000)
    assert build_session_log_path(base, started_at=started) == Path(
        "data/logs/cyxcbot.2026-06-26_14-30-52.123.log"
    )


def test_parse_retention() -> None:
    assert parse_retention("7 days") == timedelta(days=7)
    assert parse_retention("bad") == timedelta(days=7)


def test_managed_log_name_pattern() -> None:
    pattern = managed_log_name_pattern("cyxcbot", ".log")
    assert pattern.match("cyxcbot.2026-06-26_14-30-52.123.log")
    assert pattern.match(
        "cyxcbot.2026-06-26_14-30-52.123.2026-06-26_15-00-00_182160.log"
    )
    assert pattern.match("cyxcbot.archived-2026-06-26_14-30-52.123.log")
    assert pattern.match("cyxcbot.2026-06-26_00-00-00.000.log")
    assert not pattern.match("cyxcbot.access.log")
    assert not pattern.match("cyxcbot.log")


def test_prune_old_session_logs(tmp_path: Path) -> None:
    old = tmp_path / "cyxcbot.2026-01-01_00-00-00.000.log"
    recent = tmp_path / "cyxcbot.2026-06-26_00-00-00.000.log"
    old.write_text("old", encoding="utf-8")
    recent.write_text("recent", encoding="utf-8")
    old_time = time.time() - 10 * 86400
    old.touch()
    import os

    os.utime(old, (old_time, old_time))

    removed = prune_old_session_logs(
        tmp_path,
        stem="cyxcbot",
        suffix=".log",
        retention=timedelta(days=7),
    )
    assert removed == 1
    assert not old.exists()
    assert recent.exists()


def test_prune_skips_unrelated_log_files(tmp_path: Path) -> None:
    old_managed = tmp_path / "cyxcbot.2026-01-01_00-00-00.000.log"
    unrelated = tmp_path / "cyxcbot.access.log"
    old_managed.write_text("old", encoding="utf-8")
    unrelated.write_text("access", encoding="utf-8")
    old_time = time.time() - 10 * 86400
    import os

    os.utime(old_managed, (old_time, old_time))
    os.utime(unrelated, (old_time, old_time))

    removed = prune_old_session_logs(
        tmp_path,
        stem="cyxcbot",
        suffix=".log",
        retention=timedelta(days=7),
    )
    assert removed == 1
    assert not old_managed.exists()
    assert unrelated.exists()


def test_install_file_log_sink_writes_session_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "logs" / "cyxcbot.log"
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(base))
    monkeypatch.setenv("LOG_FILE_LEVEL", "INFO")
    file_sink._installed = False

    result = install_file_log_sink()
    assert result is not None
    assert result.parent == base.parent
    assert result.name.startswith("cyxcbot.")
    assert result.name.endswith(".log")
    assert result != base
    assert result.is_file()
    content = ""
    for _ in range(100):
        content = result.read_text(encoding="utf-8")
        if "文件日志已启用" in content:
            break
        time.sleep(0.02)
    assert "文件日志已启用" in content
    assert "rotation=10 MB" in content


def test_install_archives_legacy_active_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "logs" / "cyxcbot.log"
    base.parent.mkdir(parents=True)
    base.write_text("legacy session\n", encoding="utf-8")
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(base))
    file_sink._installed = False

    session_path = install_file_log_sink()
    assert session_path is not None
    assert not base.exists()
    assert list(base.parent.glob("cyxcbot.archived-*.log"))
    assert session_path.name.startswith("cyxcbot.20")


def test_archive_legacy_active_log_avoids_rename_collision(tmp_path: Path) -> None:
    base = tmp_path / "cyxcbot.log"
    base.write_text("legacy session\n", encoding="utf-8")
    moment = datetime.fromtimestamp(base.stat().st_mtime)
    ts = moment.strftime("%Y-%m-%d_%H-%M-%S") + f".{moment.microsecond // 1000:03d}"
    existing = tmp_path / f"cyxcbot.archived-{ts}.log"
    existing.write_text("already archived\n", encoding="utf-8")

    _archive_legacy_active_log(base)

    assert not base.exists()
    assert existing.exists()
    archived = [p for p in tmp_path.glob("cyxcbot.archived-*.log") if p != existing]
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "legacy session\n"


def test_install_passes_rotation_and_retention_to_loguru(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "logs" / "cyxcbot.log"
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(base))
    monkeypatch.setenv("LOG_FILE_ROTATION", "10 MB")
    monkeypatch.setenv("LOG_FILE_RETENTION", "7 days")
    file_sink._installed = False

    with patch.object(file_sink.nb_logger, "add") as mock_add:
        install_file_log_sink()
        kwargs = mock_add.call_args.kwargs
        assert kwargs["rotation"] == "10 MB"
        assert kwargs["retention"] == "7 days"


def test_install_file_log_sink_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_FILE_ENABLED", "false")
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "unused.log"))
    file_sink._installed = False

    assert install_file_log_sink() is None
    assert not list(tmp_path.glob("*.log"))


def test_install_file_log_sink_skips_on_add_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "logs" / "cyxcbot.log"
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(base))
    file_sink._installed = False

    with patch.object(file_sink.nb_logger, "add", side_effect=OSError("disk full")):
        assert install_file_log_sink() is None
    assert not base.parent.exists() or not list(base.parent.glob("cyxcbot.*.log"))
