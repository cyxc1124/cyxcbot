"""群内自助设置 QQ 专属头衔。"""

from nonebot import get_driver, on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from shared.config.service import get_config_service
from shared.group_special_title import parse_title_from_message
from shared.group_special_title_policy import daily_usage_limit_from_snapshot

from .handler import handle_group_special_title

__plugin_meta__ = PluginMetadata(
    name="群头衔设置",
    description="群成员通过命令自助设置 QQ 专属头衔",
    usage="/头衔 我的头衔 或 #头衔 我的头衔（每人每日次数见 Web Admin 群组配置）",
    type="application",
    supported_adapters={"~onebot.v11"},
)

driver = get_driver()


async def _is_group_title_command(event: Event) -> bool:
    if not isinstance(event, GroupMessageEvent):
        return False
    command_aliases = get_config_service().get_snapshot().command_aliases
    return parse_title_from_message(event.message, command_aliases) is not None


group_title_cmd = on_message(
    rule=Rule(_is_group_title_command),
    priority=5,
    block=True,
)


@driver.on_startup
async def _group_special_title_startup() -> None:
    daily_limit = daily_usage_limit_from_snapshot(get_config_service().get_snapshot())
    if daily_limit > 0:
        logger.info(
            "群头衔设置已就绪: /头衔 或 #头衔，每人每日最多 {} 次（可在 Web Admin 群组页调整）",
            daily_limit,
        )
    else:
        logger.info(
            "群头衔设置已就绪: /头衔 或 #头衔，每日次数不限制（可在 Web Admin 群组页调整）",
        )


@group_title_cmd.handle()
async def _handle_group_title(bot: Bot, event: GroupMessageEvent):
    await handle_group_special_title(bot, event)
