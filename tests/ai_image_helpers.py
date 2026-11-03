"""Initialize NoneBot without startup hooks or a production database."""

import os
import sys

import nonebot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, PrivateMessageEvent


def initialize_nonebot():
    os.environ.setdefault("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(
            sqlalchemy_database_url="sqlite+aiosqlite:///:memory:",
            alembic_startup_check=False,
        )
    if "nonebot_plugin_orm" not in sys.modules:
        nonebot.load_plugin("nonebot_plugin_orm")


initialize_nonebot()


def image_event(text="ai吗？", *, scope="group", quoted=None):
    message = Message(text)
    cls = GroupMessageEvent if scope == "group" else PrivateMessageEvent
    return cls(
        time=0,
        self_id=999,
        post_type="message",
        sub_type="normal" if scope == "group" else "friend",
        message_type=scope,
        message_id=2,
        user_id=123,
        message=message,
        original_message=message.copy(),
        raw_message=str(message),
        font=0,
        sender={"user_id": 123},
        reply=(
            {
                "time": 0,
                "message_type": scope,
                "message_id": 1,
                "real_id": 1,
                "sender": {"user_id": 123},
                "message": Message(quoted),
            }
            if quoted is not None
            else None
        ),
        **({"group_id": 456} if scope == "group" else {}),
    )
