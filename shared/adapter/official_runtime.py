"""Apply Web Admin official QQ credentials to nonebot-adapter-qq at runtime."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot

_applied_key: tuple[str, str, bool, bool] | None = None


def _mask_app_id(app_id: str) -> str:
    text = app_id.strip()
    if len(text) <= 4:
        return text
    return f"...{text[-4:]}"


def _bot_info(app_id: str, secret: str, use_websocket: bool):
    from nonebot.adapters.qq.config import BotInfo, Intents

    intents = Intents(
        guilds=False,
        guild_members=False,
        guild_messages=False,
        guild_message_reactions=False,
        direct_message=False,
        group_members=True,
        c2c_group_at_messages=True,
        message_audit=False,
        at_messages=False,
    )
    return BotInfo.model_validate(
        {
            "id": app_id,
            "token": "",
            "secret": secret,
            "intent": intents,
            "use_websocket": use_websocket,
        }
    )


def _get_adapter():
    import nonebot
    from nonebot.adapters.qq import Adapter as QQAdapter

    return nonebot.get_adapter(QQAdapter)


async def _disconnect(adapter) -> None:
    from shared.adapter.bots import iter_official_bots

    # run_bot_websocket 立刻返回，真正的网关长连接在 adapter.tasks（_forward_ws）
    tasks = getattr(adapter, "tasks", None)
    pending: list[asyncio.Task] = []
    if isinstance(tasks, set):
        pending = [task for task in list(tasks) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        tasks.clear()
    for bot in list(iter_official_bots()):
        try:
            adapter.bot_disconnect(bot)
        except Exception:
            logger.opt(exception=True).warning("断开官方 Bot {} 失败", bot.self_id)


async def apply_official_runtime(
    snapshot: AppConfigSnapshot, *, start_websocket: bool = True
) -> None:
    """Apply official QQ webhook or legacy websocket credentials."""
    global _applied_key

    app_id = (snapshot.official_qq_app_id or "").strip()
    secret = snapshot.official_qq_app_secret or ""
    sandbox = bool(snapshot.official_qq_is_sandbox)
    use_ws = bool(snapshot.official_qq_use_websocket)
    key = (app_id, secret, sandbox, use_ws)

    try:
        adapter = _get_adapter()
    except Exception:
        logger.debug("官方 QQ 适配器尚未注册，跳过热连接")
        return

    adapter.qq_config.qq_is_sandbox = sandbox

    if not app_id or not secret:
        if _applied_key is not None:
            await _disconnect(adapter)
            adapter.qq_config.qq_bots = []
            _applied_key = None
            logger.info("官方 Bot 凭证已清除，已断开连接")
        return

    from shared.adapter.bots import iter_official_bots

    if _applied_key == key:
        # Webhook 在首次有效回调后注册 Bot；同一配置无需重建。
        if not use_ws or iter_official_bots():
            return

    await _disconnect(adapter)
    info = _bot_info(app_id, secret, use_ws)
    adapter.qq_config.qq_bots = [info]
    if use_ws and start_websocket:
        task = asyncio.create_task(adapter.run_bot_websocket(info))
        adapter_tasks = getattr(adapter, "tasks", None)
        if isinstance(adapter_tasks, set):
            task.add_done_callback(adapter_tasks.discard)
            adapter_tasks.add(task)
        logger.info("官方 Bot WebSocket 已启动 AppID {}", _mask_app_id(app_id))
    elif use_ws:
        logger.info(
            "官方 Bot WebSocket 已配置 AppID {}，等待适配器启动", _mask_app_id(app_id)
        )
    else:
        logger.info(
            "官方 Bot 使用 Webhook AppID {}，等待开放平台 POST /qq/webhook（NoneBot 端口，不是 Web Admin）。本机没有公网转发时收不到消息",
            _mask_app_id(app_id),
        )
    _applied_key = key


async def on_config_reload(snapshot: AppConfigSnapshot) -> None:
    await apply_official_runtime(snapshot)
