"""群内自助设置 QQ 专属头衔。"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from shared.group_special_title import DAILY_USAGE_LIMIT

from .handler import handle_group_special_title

__plugin_meta__ = PluginMetadata(
    name="群头衔设置",
    description="群成员通过命令自助设置 QQ 专属头衔",
    usage=f"/头衔 我的头衔 或 #头衔 我的头衔（每人每日最多 {DAILY_USAGE_LIMIT} 次）",
    type="application",
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()

group_title_cmd = on_message(priority=5, block=True)


@driver.on_startup
async def _group_special_title_startup() -> None:
    logger.info(
        "群头衔设置已就绪: /头衔 或 #头衔，每人每日最多 {} 次",
        DAILY_USAGE_LIMIT,
    )


@group_title_cmd.handle()
async def _handle_group_title(bot: Bot, event: GroupMessageEvent):
    reply = await handle_group_special_title(bot, event)
    if reply is not None:
        await group_title_cmd.finish(reply)
