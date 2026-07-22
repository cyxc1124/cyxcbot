"""Rust 服务器 RCON 远程命令插件。"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.config.rust_rcon import is_qq_allowed_for_binding, match_rust_rcon_binding
from shared.config.rust_rcon_policy import is_rust_rcon_enabled
from shared.config.service import get_config_service
from utils.rust_rcon.client import RconAuthError, RconError, execute_rcon_command

__plugin_meta__ = PluginMetadata(
    name="Rust RCON",
    description="通过群内 @机器人 触发词向 Rust 服务器发送 RCON 指令",
    usage="""
在 Web Admin → 设置 → Rust RCON 配置绑定，并在群组/好友页开启 RCON 开关。

群聊：@机器人 触发词 命令（如 @机器人 rcon1 status）
私聊：触发词 命令（如 rcon1 status）
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
    logger.info(
        "Rust RCON 插件已就绪: {} 个启用绑定 / {} 个总绑定",
        enabled_count,
        len(snap.rust_rcon_bindings),
    )


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
    elif isinstance(event, PrivateMessageEvent):
        if not is_rust_rcon_enabled(snap, user_id=str(event.user_id), is_private=True):
            return
    else:
        return

    text = event.get_plaintext().strip()
    matched = match_rust_rcon_binding(text, snap.rust_rcon_bindings)
    if matched is None:
        return

    binding, command = matched
    user_id = str(event.user_id)
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
    logger.info(
        "Rust RCON 请求: {} user={} binding={} alias={} command={!r}",
        context,
        user_id,
        binding.id,
        binding.alias,
        command,
    )

    try:
        result = await execute_rcon_command(
            binding.host, binding.port, binding.password, command
        )
    except RconAuthError:
        logger.warning("Rust RCON 认证失败: binding={}", binding.id)
        await rust_rcon_cmd.finish("RCON 认证失败，请检查 Web Admin 中的密码配置")
    except RconError as exc:
        logger.warning("Rust RCON 失败: binding={} err={}", binding.id, exc)
        await rust_rcon_cmd.finish(f"RCON 执行失败：{exc}")
    except Exception:
        logger.opt(exception=True).error("Rust RCON 未预期错误: binding={}", binding.id)
        await rust_rcon_cmd.finish("RCON 执行失败，请稍后重试")

    label = binding.name or binding.alias
    await rust_rcon_cmd.finish(f"[{label}]\n{result}")
