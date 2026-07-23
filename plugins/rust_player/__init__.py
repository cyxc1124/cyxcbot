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
    parse_shop_list_page,
    parse_shop_redeem_args,
    resolve_checkin_rcon_binding,
    shop_list_trigger_hint,
)
from shared.config.service import get_config_service
from shared.rust_player import rcon_online_cache, shop_store, store
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
- 商品列表 / 商品列表2：查看积分商城商品（每页最多 20 条）
- 兑换商品 <物品ID 或 商品中文名> [数量]：消耗积分兑换游戏内物品
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
        return

    shop_page = parse_shop_list_page(text, command_aliases)
    if shop_page is not None:
        await _handle_shop_list(group_id, shop_page, command_aliases)
        return

    redeem_args = parse_shop_redeem_args(text, command_aliases)
    if redeem_args is not None:
        identifier, quantity = redeem_args
        await _handle_shop_redeem(group_id, user_id, identifier, quantity, snap)
        return


async def _fetch_status_text(rcon_binding) -> str:
    return await execute_rcon_command(
        rcon_binding.host,
        rcon_binding.port,
        rcon_binding.password,
        "status",
        truncate_response=False,
    )


async def _resolve_checkin_online(
    *,
    user_id: str,
    steam_id: str,
    rcon_binding,
    needs_rcon: bool,
) -> tuple[bool, bool]:
    """Return ``(is_online, verification_available)``."""
    if not needs_rcon:
        return False, True

    cached = rcon_online_cache.get_cached_checkin_online(user_id)
    if cached is not None:
        return cached, True

    try:
        status_text = await _fetch_status_text(rcon_binding)
    except RconAuthError:
        logger.warning(
            "Rust 签到 RCON 认证失败: binding={} user={}",
            rcon_binding.id,
            user_id,
        )
        return False, False
    except RconError:
        logger.warning(
            "Rust 签到 RCON 失败: binding={} user={}",
            rcon_binding.id,
            user_id,
        )
        return False, False
    except Exception:
        logger.opt(exception=True).error(
            "Rust 签到 RCON 未预期错误: binding={} user={}",
            rcon_binding.id,
            user_id,
        )
        return False, False

    is_online = is_steam_id_online(status_text, steam_id)
    rcon_online_cache.set_cached_checkin_online(user_id, is_online)
    return is_online, True


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
    rcon_binding = resolve_checkin_rcon_binding(
        snap.rust_rcon_bindings,
        snap.rust_checkin_rcon_binding_id,
    )
    can_claim_online_bonus = binding is not None and rcon_binding is not None
    bonus_eligible = can_claim_online_bonus and configured_bonus > 0
    check_in_state = await store.get_today_check_in_state(group_id, user_id)
    needs_rcon = store.needs_rcon_online_check(
        check_in_state, bonus_eligible=bonus_eligible
    )
    is_online = False
    online_verification_available = not needs_rcon

    if needs_rcon:
        is_online, online_verification_available = await _resolve_checkin_online(
            user_id=user_id,
            steam_id=binding.steam_id,
            rcon_binding=rcon_binding,
            needs_rcon=True,
        )

    if (
        needs_rcon
        and not online_verification_available
        and check_in_state.checked_in
        and check_in_state.online_bonus_earned == 0
    ):
        total = await store.get_group_points(group_id, user_id)
        await rust_player_cmd.finish(
            f"无法连接游戏服务器验证在线状态，请稍后重试领取在线加成 "
            f"{configured_bonus} 积分。当前积分：{total}"
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
        "Rust 签到: group={} user={} base={} bonus={} online={} bonus_only={} "
        "verified={}",
        group_id,
        user_id,
        result.base_points,
        result.online_bonus,
        is_online,
        result.bonus_only,
        online_verification_available,
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
    if bonus_eligible and not online_verification_available:
        message += "。当前无法验证游戏在线状态，请稍后重试领取在线加成"
    elif bonus_eligible and not is_online:
        message += f"。进入游戏后再次签到可领取在线加成 {configured_bonus} 积分"
    await rust_player_cmd.finish(message)


async def _handle_points_query(group_id: str, user_id: str) -> None:
    points = await store.get_group_points(group_id, user_id)
    binding = await store.get_steam_binding(user_id)
    if binding is None:
        await rust_player_cmd.finish(f"当前积分：{points}\n尚未绑定 SteamID")
    await rust_player_cmd.finish(f"当前积分：{points}\nSteamID：{binding.steam_id}")


async def _handle_shop_list(
    group_id: str,
    page: int,
    command_aliases,
) -> None:
    del group_id
    page_data = await shop_store.get_shop_list_page(page, enabled_only=True)
    trigger = shop_list_trigger_hint(command_aliases)
    if page_data.total_items == 0:
        await rust_player_cmd.finish("当前没有可兑换的商品。")

    lines = [
        f"商品列表（第 {page_data.page}/{page_data.total_pages} 页，"
        f"共 {page_data.total_items} 个商品）",
        "",
    ]
    start_index = (page_data.page - 1) * page_data.page_size + 1
    for offset, item in enumerate(page_data.items):
        index = start_index + offset
        lines.append(
            f"{index}. {item.name} — {item.points_cost} 积分（物品 ID：{item.item_id}）"
        )

    if page_data.total_pages > 1:
        if page_data.page < page_data.total_pages:
            next_page = page_data.page + 1
            lines.append("")
            lines.append(f"发送 @机器人 {trigger}{next_page} 查看第 {next_page} 页")
        else:
            lines.append("")
            lines.append(f"发送 @机器人 {trigger}1 查看第 1 页")

    await rust_player_cmd.finish("\n".join(lines))


async def _handle_shop_redeem(
    group_id: str,
    user_id: str,
    identifier: str,
    quantity: int,
    snap,
) -> None:
    binding = await store.get_steam_binding(user_id)
    if binding is None:
        trigger = bind_trigger_hint(snap.command_aliases)
        await rust_player_cmd.finish(
            f"兑换前请先绑定 SteamID，发送：{trigger} 7656119xxxxxxxxxx"
        )

    rcon_binding = resolve_checkin_rcon_binding(
        snap.rust_rcon_bindings,
        snap.rust_checkin_rcon_binding_id,
    )
    if rcon_binding is None:
        await rust_player_cmd.finish("当前未配置可用的 RCON 服务器，无法发放物品。")

    try:
        result = await shop_store.redeem_shop_item(
            group_id, user_id, identifier, quantity
        )
    except ValueError as exc:
        await rust_player_cmd.finish(str(exc))

    give_command = f"give {binding.steam_id} {result.item.item_id} {result.quantity}"
    try:
        await execute_rcon_command(
            rcon_binding.host,
            rcon_binding.port,
            rcon_binding.password,
            give_command,
        )
    except RconAuthError:
        logger.warning(
            "Rust 兑换 RCON 认证失败: binding={} user={} item={}",
            rcon_binding.id,
            user_id,
            result.item.item_id,
        )
        await shop_store.add_group_points(group_id, user_id, result.total_cost)
        await rust_player_cmd.finish("游戏服务器认证失败，积分已退回，请稍后重试。")
    except RconError:
        logger.warning(
            "Rust 兑换 RCON 结果未知: binding={} user={} item={} qty={}",
            rcon_binding.id,
            user_id,
            result.item.item_id,
            result.quantity,
        )
        await rust_player_cmd.finish(
            "无法确认物品是否发放成功（连接或响应异常），积分未退回。"
            "如未收到物品请联系管理员核实。"
        )
    except Exception:
        logger.opt(exception=True).error(
            "Rust 兑换 RCON 未预期错误: binding={} user={} item={} qty={}",
            rcon_binding.id,
            user_id,
            result.item.item_id,
            result.quantity,
        )
        await rust_player_cmd.finish(
            "发放物品时发生错误，无法确认是否成功，积分未退回。"
            "如未收到物品请联系管理员核实。"
        )

    logger.info(
        "Rust 商品兑换: group={} user={} item={} qty={} cost={} remaining={}",
        group_id,
        user_id,
        result.item.item_id,
        result.quantity,
        result.total_cost,
        result.remaining_points,
    )
    await rust_player_cmd.finish(
        f"兑换成功：{result.item.name} x{result.quantity}，"
        f"消耗 {result.total_cost} 积分，剩余 {result.remaining_points} 积分"
    )
