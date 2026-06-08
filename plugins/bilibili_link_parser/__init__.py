"""
B 站链接自动解析插件

自动识别群聊/私聊中的视频链接、直播间链接与 b23.tv 短链，
并回复封面、标题、UP 主/主播、时间信息与链接。
"""

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from utils.bilibili_api import api_manager as live_api_manager
from utils.bilibili_api import extract_bilibili_refs, video_api_manager

from .config import Config, get_config, reload_config
from .message_text import collect_message_text
from .sender import build_live_link_message, build_video_link_message

__plugin_meta__ = PluginMetadata(
    name="B 站链接解析",
    description="自动解析群聊/私聊中的 B 站视频与直播链接",
    usage="发送含 BV 号、直播间链接或 b23.tv 短链的消息即可触发",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

group_link_parser = on_message(priority=4, block=False)
private_link_parser = on_message(priority=4, block=False)


async def _resolve_reply(config: Config, message_text: str):
    cookie = config.bilibili_cookie or None
    if not cookie:
        logger.warning("B 站链接解析：未配置 Cookie，直播接口可能返回 -352 或解析失败")

    await video_api_manager.init(cookie)
    await live_api_manager.init(cookie)
    session = video_api_manager.api.session
    refs = await extract_bilibili_refs(message_text, session, cookie=cookie)
    if not refs:
        logger.debug(f"B 站链接解析：未识别到链接，text={message_text[:120]!r}")
        return None

    for ref in refs:
        try:
            if ref.kind == "video":
                video = await video_api_manager.get_video_detail(bvid=ref.bvid, aid=ref.aid)
                if video:
                    return build_video_link_message(video, config.message_templates)
            elif ref.room_id:
                room_info, user_info = await live_api_manager.get_room_and_user_info(ref.room_id)
                if room_info:
                    return build_live_link_message(room_info, user_info, config.message_templates)
        except Exception as exc:
            logger.warning(f"B 站链接解析失败 ref={ref}: {exc}")

    logger.warning(f"B 站链接解析：API 未返回有效内容 refs={refs}")
    return None


async def _handle_link_message(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> None:
    config = get_config()
    if not config.enabled:
        return

    if isinstance(event, PrivateMessageEvent):
        if not config.enable_private:
            return
    elif isinstance(event, GroupMessageEvent):
        if str(event.user_id) == str(event.self_id):
            return

    message_text = collect_message_text(event)
    if not message_text:
        return

    logger.info(f"B 站链接解析：收到消息 user={event.user_id} text={message_text[:120]!r}")

    reply = await _resolve_reply(config, message_text)
    if reply is None:
        return

    try:
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_msg(group_id=event.group_id, message=reply)
        else:
            await bot.send_private_msg(user_id=event.user_id, message=reply)
        logger.info(
            f"已回复 B 站链接解析: user={event.user_id}, "
            f"{'group=' + str(event.group_id) if isinstance(event, GroupMessageEvent) else 'private'}"
        )
    except Exception as exc:
        logger.error(f"发送 B 站链接解析结果失败: {exc}")


@group_link_parser.handle()
async def handle_group_link(bot: Bot, event: GroupMessageEvent):
    await _handle_link_message(bot, event)


@private_link_parser.handle()
async def handle_private_link(bot: Bot, event: PrivateMessageEvent):
    await _handle_link_message(bot, event)


async def _on_config_reload(_snapshot) -> None:
    reload_config()


def _register_config_reload() -> None:
    try:
        from shared.config.service import get_config_service

        get_config_service().register_reload_callback(_on_config_reload)
    except Exception as exc:
        logger.warning(f"B 站链接解析：配置热重载注册失败: {exc}")


driver = get_driver()


@driver.on_startup
async def _link_parser_startup() -> None:
    _register_config_reload()
