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
    resolve_checkin_rcon_binding,
)
from shared.config.service import get_config_service
from shared.rust_player import store
from utils.rust_rcon.client import RconAuthError, RconError, execute_rcon_command
from utils.rust_rcon.status import is_steam_id_online

__plugin_meta__ = PluginMetadata(
    name="Rust 群积分",
    description="群内签到、积分查询与 SteamID 绑定",
    usage="""
群聊 @机器人（触发词可在 Web Admin → Rust 远控 → 群管命令 中自定义）：
- 绑定 <SteamID64>：绑定 Steam 账号（不可自助换绑）
- 签到：每日签到获取随机积分；已绑定 SteamID 且在游戏内在线时可领取/补领在线加成
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
        "Rust 群积分插件已就绪: 签到积分 {}–{}，在线加成 {}",
        snap.rust_checkin_points_min,
        snap.rust_checkin_points_max,
        snap.rust_checkin_online_bonus_points,
    )


@rust_player_cmd.handle()
async def handle_rust_player(bot: Bot, event: GroupMessageEvent) -> None:
    if not isinstance(event, GroupMessageEvent):
        return
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
        await _handle_checkin(group_id, user_id)
        return


async def _handle_checkin(group_id: str, user_id: str) -> None:
    snap = get_config_service().get_snapshot()
    binding = await store.get_steam_binding(user_id)
    configured_bonus = snap.rust_checkin_online_bonus_points
    can_claim_online_bonus = binding is not None
    is_online = False
    rcon_binding = resolve_checkin_rcon_binding(
        snap.rust_rcon_bindings,
        snap.rust_checkin_rcon_binding_id,
    )

    if can_claim_online_bonus and rcon_binding is not None:
        try:
            status_text = await execute_rcon_command(
                rcon_binding.host,
                rcon_binding.port,
                rcon_binding.password,
                "status",
            )
            is_online = is_steam_id_online(status_text, binding.steam_id)
        except RconAuthError:
            logger.warning(
                "Rust 签到 RCON 认证失败: binding={} user={}",
                rcon_binding.id,
                user_id,
            )
        except RconError:
            logger.warning(
                "Rust 签到 RCON 失败: binding={} user={}",
                rcon_binding.id,
                user_id,
            )
        except Exception:
            logger.opt(exception=True).error(
                "Rust 签到 RCON 未预期错误: binding={} user={}",
                rcon_binding.id,
                user_id,
            )

    result = await store.perform_check_in(
        group_id,
        user_id,
        min_points=snap.rust_checkin_points_min,
        max_points=snap.rust_checkin_points_max,
        configured_online_bonus=configured_bonus,
        is_online=is_online,
        can_claim_online_bonus=can_claim_online_bonus,
    )

    if result.already_checked_in:
        await rust_player_cmd.finish(
            f"你今天已经签到过了，当前积分：{result.total_points}"
        )
    if result.bonus_pending:
        await rust_player_cmd.finish(
            f"你已签到获得基础积分，当前积分：{result.total_points}。"
            f"进入游戏后再次签到可领取在线加成 {configured_bonus} 积分"
        )

    logger.info(
        "Rust 签到: group={} user={} base={} bonus={} online={} bonus_only={}",
        group_id,
        user_id,
        result.base_points,
        result.online_bonus,
        is_online,
        result.bonus_only,
    )

    if result.bonus_only:
        await rust_player_cmd.finish(
            f"在线加成补发成功，获得 {result.online_bonus} 积分，"
            f"当前积分：{result.total_points}"
        )
    if result.online_bonus > 0:
        await rust_player_cmd.finish(
            f"签到成功，获得 {result.base_points} 积分"
            f" + 在线加成 {result.online_bonus} 积分，"
            f"当前积分：{result.total_points}"
        )

    message = (
        f"签到成功，获得 {result.base_points} 积分，当前积分：{result.total_points}"
    )
    if can_claim_online_bonus and configured_bonus > 0:
        message += f"。进入游戏后再次签到可领取在线加成 {configured_bonus} 积分"
    await rust_player_cmd.finish(message)


async def _handle_points_query(group_id: str, user_id: str) -> None:
    points = await store.get_group_points(group_id, user_id)
    binding = await store.get_steam_binding(user_id)
    if binding is None:
        await rust_player_cmd.finish(f"当前积分：{points}\n尚未绑定 SteamID")
    await rust_player_cmd.finish(f"当前积分：{points}\nSteamID：{binding.steam_id}")
