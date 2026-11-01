"""按机器人、会话和用户暂存分 P 选择，记录不跨进程保存。"""

from __future__ import annotations

from asyncio import Lock
from time import monotonic
from weakref import WeakValueDictionary

from shared.adapter.inbound import group_id_of, user_id_of
from utils.bilibili_api import VideoInfo

type SelectionKey = tuple[str, str, str | None, str]

_TTL = 300
_MAX_PENDING = 512
_pending: dict[SelectionKey, tuple[float, VideoInfo]] = {}
_locks: WeakValueDictionary[SelectionKey, Lock] = WeakValueDictionary()


def selection_key(bot, event) -> SelectionKey:
    return (
        bot.adapter.get_name(),
        str(bot.self_id),
        group_id_of(event),
        user_id_of(event),
    )


def pending_video(key: SelectionKey) -> VideoInfo | None:
    now = monotonic()
    for expired in [key for key, (deadline, _) in _pending.items() if deadline <= now]:
        _pending.pop(expired)
    record = _pending.get(key)
    return record[1] if record else None


def selection_lock(key: SelectionKey) -> Lock:
    return _locks.setdefault(key, Lock())


def remember_video(key: SelectionKey, video: VideoInfo) -> None:
    pending_video(key)
    forget_video(key)
    if len(_pending) >= _MAX_PENDING:
        _pending.pop(next(iter(_pending)))
    _pending[key] = (monotonic() + _TTL, video)


def forget_video(key: SelectionKey) -> None:
    _pending.pop(key, None)
