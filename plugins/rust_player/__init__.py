"""Rust 群积分、签到与 SteamID 绑定插件。"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.rust_player import (
    bind_trigger_hint,
    is_bind_command,
    is_checkin_command,
    is_points_query_command,
    parse_bind_steam_id,
)
from shared.config.service import get_config_service
from shared.rust_player import store

__plugin_meta__ = PluginMetadata(
    name="Rust 群积分",
    description="群内签到、积分查询与 SteamID 绑定",
    usage="""
群聊 @机器人（触发词可在 Web Admin → Rust 远控 → 群管命令 中自定义）：
- 绑定 <SteamID64>：绑定 Steam 账号（不可自助换绑）
- 签到：每日签到获取随机积分
- 我的积分 / 积分：查询本群积分
""",
    type="application",
    homepage="https://github.com/cyxc1124/cyxcbot",
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()
rust_player_cmd = on_message(priority=10, block=False)


@driver.on_startup
async def _rust_player_startup() -> None:
    snap = get_config_service().get_snapshot()
    logger.info(
        "Rust 群积分插件已就绪: 签到积分 {}–{}",
        snap.rust_checkin_points_min,
        snap.rust_checkin_points_max,
    )


@rust_player_cmd.handle()
async def handle_rust_player(bot: Bot, event: GroupMessageEvent) -> None:
    if not event.is_tome():
        return

    snap = get_config_service().get_snapshot()
    command_aliases = snap.command_aliases
    text = event.get_plaintext().strip()
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    if (
        is_bind_command(text, command_aliases)
        or parse_bind_steam_id(text, command_aliases) is not None
        or is_checkin_command(text, command_aliases)
    ):
        await _handle_bind_or_checkin(
            bot, event, text, group_id, user_id, command_aliases
        )
        return

    if is_points_query_command(text, command_aliases):
        await _handle_points_query(group_id, user_id)


async def _handle_bind_or_checkin(
    bot: Bot,
    event: GroupMessageEvent,
    text: str,
    group_id: str,
    user_id: str,
    command_aliases,
) -> None:
    steam_id = parse_bind_steam_id(text, command_aliases)
    if is_bind_command(text, command_aliases):
        if steam_id is None:
            trigger = bind_trigger_hint(command_aliases)
            await rust_player_cmd.finish(
                f"SteamID 格式无效，请发送：{trigger} 7656119xxxxxxxxxx"
            )
        try:
            await store.create_steam_binding(user_id, steam_id)
        except ValueError as exc:
            await rust_player_cmd.finish(str(exc))
        logger.info("Rust Steam 绑定: group={} user={}", group_id, user_id)
        await rust_player_cmd.finish(f"SteamID 绑定成功：{steam_id}")
        return

    if steam_id is not None:
        return

    if is_checkin_command(text, command_aliases):
        snap = get_config_service().get_snapshot()
        result = await store.perform_check_in(
            group_id,
            user_id,
            min_points=snap.rust_checkin_points_min,
            max_points=snap.rust_checkin_points_max,
        )
        if result.already_checked_in:
            await rust_player_cmd.finish(
                f"你今天已经签到过了，当前积分：{result.total_points}"
            )
        logger.info(
            "Rust 签到: group={} user={} points={}",
            group_id,
            user_id,
            result.points_earned,
        )
        await rust_player_cmd.finish(
            f"签到成功，获得 {result.points_earned} 积分，当前积分：{result.total_points}"
        )


async def _handle_points_query(group_id: str, user_id: str) -> None:
    points = await store.get_group_points(group_id, user_id)
    binding = await store.get_steam_binding(user_id)
    if binding is None:
        await rust_player_cmd.finish(f"当前积分：{points}\n尚未绑定 SteamID")
    await rust_player_cmd.finish(f"当前积分：{points}\nSteamID：{binding.steam_id}")
