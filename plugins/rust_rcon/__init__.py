"""Rust 服务器 RCON 远程命令插件。"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.rust_rcon import is_qq_allowed_for_binding, match_rust_rcon_binding
from shared.config.rust_rcon_custom import (
    match_rust_rcon_custom_command,
    render_custom_command_template,
    resolve_steamid_target,
    template_needs_steamid,
)
from shared.config.rust_rcon_policy import is_rust_rcon_enabled
from shared.config.service import get_config_service
from shared.notify.message_template import safe_text_message
from shared.rust_player import store
from utils.rust_rcon.client import (
    RconAuthError,
    RconError,
    execute_rcon_command,
    summarize_rcon_command_for_log,
)

__plugin_meta__ = PluginMetadata(
    name="Rust RCON",
    description="通过群内 @机器人 触发词向 Rust 服务器发送 RCON 指令",
    usage="""
在 Web Admin → 设置 → Rust RCON 配置绑定，并在群组/好友页开启 RCON 开关。

群聊：@机器人 触发词 命令（如 @机器人 rcon1 status）
私聊：触发词 命令（如 rcon1 status）
自定义指令：@机器人 指令名 @群用户 或 @机器人 指令名 SteamID64
""",
    type="application",
    homepage="https://github.com/cyxc1124/cyxcbot",
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()
rust_rcon_cmd = on_message(priority=10, block=False)


@driver.on_startup
async def _rust_rcon_startup() -> None:
    snap = get_config_service().get_snapshot()
    enabled_count = sum(1 for binding in snap.rust_rcon_bindings if binding.enabled)
    custom_count = sum(
        1 for command in snap.rust_rcon_custom_commands if command.enabled
    )
    logger.info(
        "Rust RCON 插件已就绪: {} 个启用绑定 / {} 个总绑定，{} 个启用自定义指令",
        enabled_count,
        len(snap.rust_rcon_bindings),
        custom_count,
    )


def _mentioned_user_ids(event: GroupMessageEvent) -> list[str]:
    self_id = str(event.self_id)
    result: list[str] = []
    for segment in event.message:
        if segment.type != "at":
            continue
        qq = str(segment.data.get("qq", "")).strip()
        if not qq or qq == "all" or qq == self_id:
            continue
        if qq not in result:
            result.append(qq)
    return result


async def _execute_and_reply(
    *,
    binding,
    command: str,
    context: str,
    user_id: str,
    label: str,
) -> None:
    logger.info(
        "Rust RCON 请求: {} user={} binding={} alias={} command={}",
        context,
        user_id,
        binding.id,
        binding.alias,
        summarize_rcon_command_for_log(command),
    )

    try:
        result = await execute_rcon_command(
            binding.host, binding.port, binding.password, command
        )
    except RconAuthError:
        logger.warning("Rust RCON 认证失败: binding={}", binding.id)
        await rust_rcon_cmd.finish("RCON 认证失败，请检查 Web Admin 中的密码配置")
    except RconError:
        logger.warning("Rust RCON 失败: binding={}", binding.id)
        await rust_rcon_cmd.finish("RCON 执行失败，请检查绑定配置或稍后重试")
    except Exception:
        logger.opt(exception=True).error("Rust RCON 未预期错误: binding={}", binding.id)
        await rust_rcon_cmd.finish("RCON 执行失败，请稍后重试")

    await rust_rcon_cmd.finish(safe_text_message(f"[{label}]\n{result}"))


async def _handle_custom_command(
    event: GroupMessageEvent,
    text: str,
    snap,
) -> bool:
    """Handle custom command when matched. Returns True if handled."""
    enabled_binding_ids = {
        binding.id for binding in snap.rust_rcon_bindings if binding.enabled
    }
    matched = match_rust_rcon_custom_command(
        text,
        snap.rust_rcon_custom_commands,
        enabled_binding_ids=enabled_binding_ids,
    )
    if matched is None:
        return False

    command, remainder = matched
    binding = next(
        (item for item in snap.rust_rcon_bindings if item.id == command.binding_id),
        None,
    )
    if binding is None or not binding.enabled:
        return False

    user_id = str(event.user_id)
    # 与任意 RCON 命令一致：绑定级 QQ 白名单；不在名单时静默忽略。
    if not is_qq_allowed_for_binding(binding, user_id):
        return True

    steam_id: str | None = None
    if template_needs_steamid(command.template):
        kind, value = resolve_steamid_target(remainder, _mentioned_user_ids(event))
        if kind is None:
            await rust_rcon_cmd.finish(
                f"请提供目标：{command.name} @群用户 或 {command.name} SteamID64"
            )
        if kind == "invalid_steamid":
            await rust_rcon_cmd.finish(
                "SteamID 格式无效，请使用 17 位 SteamID64（7656119xxxxxxxxxx）"
            )
        if kind == "qq":
            binding_row = await store.get_steam_binding(value)
            if binding_row is None:
                await rust_rcon_cmd.finish(
                    f"QQ {value} 未绑定 SteamID，请先让对方完成绑定"
                )
            steam_id = binding_row.steam_id
        else:
            steam_id = value

    try:
        rcon_command = render_custom_command_template(command.template, steam_id)
    except ValueError as exc:
        await rust_rcon_cmd.finish(str(exc))

    label = command.name
    context = f"group={event.group_id}"
    await _execute_and_reply(
        binding=binding,
        command=rcon_command,
        context=context,
        user_id=user_id,
        label=label,
    )
    return True


@rust_rcon_cmd.handle()
async def handle_rust_rcon(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> None:
    snap = get_config_service().get_snapshot()

    if isinstance(event, GroupMessageEvent):
        if not event.is_tome():
            return
        if not is_rust_rcon_enabled(snap, group_id=str(event.group_id)):
            return
        text = event.get_plaintext().strip()
        if await _handle_custom_command(event, text, snap):
            return
    elif isinstance(event, PrivateMessageEvent):
        if not is_rust_rcon_enabled(snap, user_id=str(event.user_id), is_private=True):
            return
        text = event.get_plaintext().strip()
    else:
        return

    matched = match_rust_rcon_binding(text, snap.rust_rcon_bindings)
    if matched is None:
        return

    binding, command = matched
    user_id = str(event.user_id)
    # 绑定级 QQ 白名单仅约束此处任意 RCON 命令；积分商城 giveto 见 rust_player._handle_shop_redeem。
    if not is_qq_allowed_for_binding(binding, user_id):
        return

    if not command:
        await rust_rcon_cmd.finish(
            f"请在触发词后输入 RCON 命令，例如：{binding.alias} status"
        )

    context = (
        f"group={event.group_id}"
        if isinstance(event, GroupMessageEvent)
        else f"user={event.user_id}"
    )
    label = binding.name or binding.alias
    await _execute_and_reply(
        binding=binding,
        command=command,
        context=context,
        user_id=user_id,
        label=label,
    )
