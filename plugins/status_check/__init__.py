"""
机器人状态查询插件
仅允许特定QQ号查询机器人运行状态
"""

from nonebot import get_driver
from nonebot.log import logger

from shared.config.service import get_config_service

from . import status_checker  # noqa: F401

__plugin_meta__ = {
    "name": "机器人状态查询",
    "description": "仅允许特定QQ号查询机器人运行状态",
    "usage": "/status - 查询机器人运行状态",
    "version": "1.0.0",
    "author": "cyxcbot",
}

driver = get_driver()


@driver.on_startup
async def _status_check_startup() -> None:
    snap = get_config_service().get_snapshot()
    allowed = len(snap.status_check_allowed_qq)
    superusers = len(snap.nonebot_superusers)
    logger.info(
        f"状态查询插件已就绪: 专用白名单 {allowed} 人, 超级用户 {superusers} 人, "
        f"详细={'开' if snap.status_check_show_detailed else '关'}"
    )
