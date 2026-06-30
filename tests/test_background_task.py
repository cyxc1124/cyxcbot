"""Tests for shared monitor background task exception logging (issue #98)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from shared.monitor.background_task import spawn_background_task


def _patch_logger(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    error_mock = MagicMock()
    opt_mock = MagicMock(return_value=MagicMock(error=error_mock))
    logger_mock = MagicMock(opt=opt_mock)
    monkeypatch.setattr("shared.monitor.background_task.logger", logger_mock)
    return error_mock


@pytest.mark.asyncio
async def test_spawn_background_task_logs_exception(monkeypatch):
    error_mock = _patch_logger(monkeypatch)

    async def fail() -> None:
        raise RuntimeError("boom")

    task = spawn_background_task("test task", fail())
    await asyncio.wait({task})

    error_mock.assert_called_once_with("后台任务 {} 失败", "test task")


@pytest.mark.asyncio
async def test_spawn_background_task_deferred_name_args(monkeypatch):
    error_mock = _patch_logger(monkeypatch)

    async def fail() -> None:
        raise RuntimeError("boom")

    task = spawn_background_task("persist {}", fail(), name_args=("123",))
    await asyncio.wait({task})

    error_mock.assert_called_once_with("后台任务 {} 失败", "persist 123")


@pytest.mark.asyncio
async def test_spawn_background_task_success_is_silent(monkeypatch):
    error_mock = _patch_logger(monkeypatch)

    async def ok() -> None:
        return None

    spawn_background_task("ok task", ok())
    await asyncio.sleep(0)

    error_mock.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_background_task_cancelled_is_silent(monkeypatch):
    error_mock = _patch_logger(monkeypatch)

    async def hang() -> None:
        await asyncio.Event().wait()

    task = spawn_background_task("cancel task", hang())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    error_mock.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_background_task_tracks_task_set():
    tasks: set[asyncio.Task] = set()

    async def ok() -> None:
        return None

    task = spawn_background_task("tracked task", ok(), tasks=tasks)
    assert task in tasks
    await task
    assert task not in tasks
