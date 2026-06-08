"""全局拦截已关闭「处理群消息」的 QQ 群，使其不再响应任何命令。"""

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.exception import IgnoredException
from nonebot.log import logger
from nonebot.message import event_preprocessor
from nonebot.plugin import PluginMetadata

from shared.config.service import get_config_service
from shared.group_policy import is_group_message_enabled_from_snapshot

__plugin_meta__ = PluginMetadata(
    name="群组消息守卫",
    description="关闭处理群消息的 QQ 群不再响应任何命令",
    usage="在 Web Admin 群组管理中配置",
    type="application",
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()


@driver.on_startup
async def _log_group_guard_policy() -> None:
    snap = get_config_service().get_snapshot()
    if snap.message_group_restrict:
        logger.info(
            f"群组消息守卫: 白名单模式, 允许 {len(snap.message_enabled_group_ids)} 个群"
        )
    else:
        logger.info("群组消息守卫: 未限制, 所有群消息均可处理")


@event_preprocessor
async def block_disabled_group_messages(event) -> None:
    """在命令匹配前丢弃已关闭消息处理的群消息。"""
    if not isinstance(event, GroupMessageEvent):
        return

    group_id = str(event.group_id)
    if not is_group_message_enabled_from_snapshot(
        group_id,
        get_config_service().get_snapshot(),
    ):
        logger.debug(f"群组 {group_id} 已关闭消息处理，忽略群消息")
        raise IgnoredException(f"group {group_id} message processing disabled")
