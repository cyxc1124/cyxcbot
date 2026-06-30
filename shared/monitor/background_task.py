"""Fire-and-forget asyncio tasks with unified exception logging."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, Optional, Set, TypeVar

from nonebot.log import logger

T = TypeVar("T")


def _format_task_name(name: str, name_args: tuple[Any, ...]) -> str:
    if not name_args:
        return name
    return name.format(*name_args)


def _log_task_exception(
    name: str,
    task: asyncio.Task,
    *,
    name_args: tuple[Any, ...] = (),
) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.opt(exception=exc).error(
            "后台任务 {} 失败",
            _format_task_name(name, name_args),
        )


def spawn_background_task(
    name: str,
    coro: Coroutine[None, None, T],
    *,
    name_args: tuple[Any, ...] = (),
    tasks: Optional[Set[asyncio.Task]] = None,
) -> asyncio.Task:
    """Spawn a fire-and-forget task; log uncaught exceptions on completion."""
    task = asyncio.create_task(coro)
    if tasks is not None:
        tasks.add(task)

    def _on_done(done_task: asyncio.Task) -> None:
        if tasks is not None:
            tasks.discard(done_task)
        _log_task_exception(name, done_task, name_args=name_args)

    task.add_done_callback(_on_done)
    return task
