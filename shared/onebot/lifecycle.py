"""OneBot connection lifecycle helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nonebot import get_bots
from nonebot.log import logger


async def stop_monitor_if_no_bots(
    stop_fn: Callable[[], Awaitable[Any]],
    *,
    bot_self_id: str,
    monitor_name: str,
) -> bool:
    """Stop *monitor_name* only when no OneBot remains connected.

  NoneBot removes the disconnecting bot from ``get_bots()`` before
  ``on_bot_disconnect`` hooks run, so a non-empty dict means another session
  is still online.

  Returns True when *stop_fn* was invoked.
    """
    remaining = get_bots()
    if remaining:
        logger.info(
            "机器人 {} 断开连接，仍有 {} 个 Bot 在线，{} 继续运行",
            bot_self_id,
            len(remaining),
            monitor_name,
        )
        return False

    logger.info("机器人 {} 断开连接，无可用 Bot，正在停止{}...", bot_self_id, monitor_name)
    await stop_fn()
    return True
