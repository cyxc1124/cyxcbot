"""Classify connected NoneBot bots. Ignore Console; official QQ is not OneBot."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def is_console_bot(bot: Any) -> bool:
    try:
        from nonebot.adapters.console import Bot as ConsoleBot
    except ImportError:
        return False
    return isinstance(bot, ConsoleBot)


def is_official_qq_bot(bot: Any) -> bool:
    try:
        from nonebot.adapters.qq import Bot as QQBot
    except ImportError:
        return False
    return isinstance(bot, QQBot)


def is_onebot_v11_bot(bot: Any) -> bool:
    if is_console_bot(bot) or is_official_qq_bot(bot):
        return False
    try:
        from nonebot.adapters.onebot.v11 import Bot as OneBotBot
    except ImportError:
        return False
    return isinstance(bot, OneBotBot)


def is_messaging_bot(bot: Any) -> bool:
    """Bots that may start monitors. Console is ignored."""
    return not is_console_bot(bot)


def iter_connected_bots() -> Iterator[Any]:
    from nonebot import get_bots

    yield from get_bots().values()


def iter_onebot_bots() -> list[Any]:
    """OneBot V11 plus test doubles; excludes Console and official QQ."""
    return [
        bot
        for bot in iter_connected_bots()
        if not is_console_bot(bot) and not is_official_qq_bot(bot)
    ]


def iter_official_bots() -> list[Any]:
    return [bot for bot in iter_connected_bots() if is_official_qq_bot(bot)]


def messaging_bots() -> list[Any]:
    return [bot for bot in iter_connected_bots() if is_messaging_bot(bot)]
