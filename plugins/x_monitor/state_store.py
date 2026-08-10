"""X 监控运行时状态的 DB 持久化。"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import XMonitorState
from utils.x_api.models import tweet_id_as_int

from .delivery_retry import decode_pending_ids, encode_pending_ids

PendingDelivery = Tuple[str, List[str], List[str]]


class XMonitorStateStore:
    """负责 XMonitor 运行时状态的加载、持久化与删除。"""

    async def load(
        self,
        *,
        usernames: list[str],
        last_tweet_ids: Dict[str, str],
        initialized_usernames: Dict[str, bool],
        pending_tweet_delivery: Dict[str, PendingDelivery],
    ) -> None:
        if not usernames:
            return

        async with get_session() as session:
            async with session.begin():
                rows = (
                    await session.scalars(
                        select(XMonitorState).where(
                            XMonitorState.username.in_(usernames)
                        )
                    )
                ).all()
                by_username = {row.username: row for row in rows}

                for username in usernames:
                    row = by_username.get(username)
                    if row:
                        last_tweet_ids[username] = row.last_tweet_id or "0"
                        initialized = bool(row.initialized)
                        # 旧状态：initialized 但游标为 0 → 视为未初始化，避免零游标翻页群发
                        if initialized and not tweet_id_as_int(
                            last_tweet_ids[username]
                        ):
                            initialized = False
                        initialized_usernames[username] = initialized
                        tweet_id = (row.pending_tweet_id or "").strip()
                        groups = decode_pending_ids(row.pending_group_ids)
                        users = decode_pending_ids(row.pending_user_ids)
                        if tweet_id and (groups or users):
                            pending_tweet_delivery[username] = (
                                tweet_id,
                                groups,
                                users,
                            )
                        else:
                            pending_tweet_delivery.pop(username, None)
                    else:
                        last_tweet_ids[username] = "0"
                        initialized_usernames[username] = False
                        pending_tweet_delivery.pop(username, None)

    async def persist(
        self,
        username: str,
        *,
        last_tweet_ids: Dict[str, str],
        initialized_usernames: Dict[str, bool],
        pending_tweet_delivery: Dict[str, PendingDelivery],
        check_still_valid: Optional[Callable[[], bool]] = None,
    ) -> None:
        if check_still_valid is not None and not check_still_valid():
            return
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XMonitorState, username)
                if not row:
                    row = XMonitorState(username=username)
                    session.add(row)
                row.last_tweet_id = last_tweet_ids.get(username, "0")
                row.initialized = initialized_usernames.get(username, False)
                pending = pending_tweet_delivery.get(username)
                if pending:
                    row.pending_tweet_id = pending[0]
                    row.pending_group_ids = encode_pending_ids(pending[1])
                    row.pending_user_ids = encode_pending_ids(pending[2])
                else:
                    row.pending_tweet_id = None
                    row.pending_group_ids = ""
                    row.pending_user_ids = ""

    async def delete(self, username: str) -> None:
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XMonitorState, username)
                if row:
                    await session.delete(row)
