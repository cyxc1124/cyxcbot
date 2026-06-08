"""全局拦截已关闭「处理私聊消息」的 QQ 用户，使其不再响应任何私聊指令。"""

from nonebot.adapters.onebot.v11 import PrivateMessageEvent
from nonebot.exception import IgnoredException
from nonebot.log import logger
from nonebot.message import event_preprocessor
from nonebot.plugin import PluginMetadata

from shared.config.service import get_config_service
from shared.private_policy import is_private_message_enabled_from_snapshot

__plugin_meta__ = PluginMetadata(
    name="私聊消息守卫",
    description="关闭处理私聊消息的好友不再响应任何私聊命令",
    usage="在 Web Admin 私聊管理中配置",
    type="application",
    supported_adapters={"~onebot.v11"},
)


@event_preprocessor
async def block_disabled_private_messages(event) -> None:
    """在命令匹配前丢弃已关闭消息处理的好友私聊。"""
    if not isinstance(event, PrivateMessageEvent):
        return

    user_id = str(event.user_id)
    if not is_private_message_enabled_from_snapshot(
        user_id,
        get_config_service().get_snapshot(),
    ):
        logger.debug(f"用户 {user_id} 已关闭私聊消息处理，忽略私聊")
        raise IgnoredException(f"user {user_id} private message processing disabled")
