"""全局拦截已关闭「处理好友消息」的 QQ 用户，使其不再响应任何好友指令。"""

from nonebot import get_driver
from nonebot.exception import IgnoredException
from nonebot.log import logger
from nonebot.message import event_preprocessor
from nonebot.plugin import PluginMetadata

from shared.adapter.inbound import is_official_c2c_event, is_private_event, user_id_of
from shared.adapter.sessions import remember_official_session
from shared.config.service import get_config_service
from shared.private_policy import is_private_message_enabled_from_snapshot

__plugin_meta__ = PluginMetadata(
    name="好友消息守卫",
    description="关闭处理好友消息的好友不再响应任何好友命令",
    usage="在 Web Admin 好友管理中配置",
    type="application",
    supported_adapters={"~onebot.v11", "~qq"},
)

driver = get_driver()


@driver.on_startup
async def _log_private_guard_policy() -> None:
    snap = get_config_service().get_snapshot()
    if snap.message_private_restrict:
        logger.info(
            f"好友消息守卫: 白名单模式, 允许 {len(snap.message_enabled_user_ids)} 个好友"
        )
    else:
        logger.info("好友消息守卫: 未限制, 所有好友消息均可处理")


@event_preprocessor
async def block_disabled_private_messages(event) -> None:
    """在命令匹配前丢弃已关闭消息处理的好友消息。"""
    if not is_private_event(event):
        return

    user_id = user_id_of(event)
    if not user_id:
        return
    if is_official_c2c_event(event):
        await remember_official_session(event)
    if not is_private_message_enabled_from_snapshot(
        user_id,
        get_config_service().get_snapshot(),
    ):
        if is_official_c2c_event(event):
            logger.info(
                "官方用户 {} 未启用好友消息，已忽略。请在好友页打开后再发私聊",
                user_id,
            )
        else:
            logger.debug(f"用户 {user_id} 已关闭好友消息处理，忽略好友消息")
        raise IgnoredException(f"user {user_id} private message processing disabled")
