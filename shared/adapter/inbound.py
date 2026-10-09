"""Extract group/user/plaintext from OneBot or official QQ events."""

from __future__ import annotations

from typing import Any


def _openid_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def is_official_group_event(event: Any) -> bool:
    return _openid_text(getattr(event, "group_openid", None)) is not None


def is_official_c2c_event(event: Any) -> bool:
    if is_official_group_event(event):
        return False
    if getattr(event, "group_id", None) is not None:
        return False
    author = getattr(event, "author", None)
    if author is None:
        return False
    return (
        _openid_text(getattr(author, "user_openid", None)) is not None
        or _openid_text(getattr(author, "id", None)) is not None
    )


def is_group_event(event: Any) -> bool:
    if is_official_group_event(event):
        return True
    try:
        from nonebot.adapters.onebot.v11 import GroupMessageEvent

        if isinstance(event, GroupMessageEvent):
            return True
    except ImportError:
        pass
    return getattr(event, "group_id", None) is not None


def is_private_event(event: Any) -> bool:
    if is_official_group_event(event):
        return False
    if is_official_c2c_event(event):
        return True
    try:
        from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

        if isinstance(event, GroupMessageEvent):
            return False
        if isinstance(event, PrivateMessageEvent):
            return True
    except ImportError:
        pass
    if getattr(event, "group_id", None) is not None:
        return False
    return getattr(event, "user_id", None) is not None


def group_id_of(event: Any) -> str | None:
    openid = _openid_text(getattr(event, "group_openid", None))
    if openid:
        return openid
    group_id = getattr(event, "group_id", None)
    if group_id is None:
        return None
    return str(group_id)


def user_id_of(event: Any) -> str:
    openid = _openid_text(getattr(event, "openid", None))
    if openid:
        return openid
    author = getattr(event, "author", None)
    if author is not None:
        for attr in ("member_openid", "user_openid", "id"):
            value = _openid_text(getattr(author, attr, None))
            if value:
                return value
    user_id = getattr(event, "user_id", None)
    return str(user_id) if user_id is not None else ""


def plaintext_of(event: Any) -> str:
    getter = getattr(event, "get_plaintext", None)
    if callable(getter):
        return str(getter() or "").strip()
    return str(getattr(event, "get_message", lambda: "")() or "").strip()


def is_tome(event: Any) -> bool:
    if is_official_group_event(event) or is_official_c2c_event(event):
        return True
    checker = getattr(event, "is_tome", None)
    if callable(checker):
        return bool(checker())
    return False


def event_msg_id(event: Any) -> str | None:
    value = getattr(event, "id", None)
    return str(value) if value else None
