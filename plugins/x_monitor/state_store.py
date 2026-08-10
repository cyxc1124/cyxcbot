"""X 监控运行时状态的 DB 持久化。"""

from typing import Callable, Dict, Optional

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import XMonitorState


class XMonitorStateStore:
    """负责 XMonitor 运行时状态的加载、持久化与删除。"""

    async def load(
        self,
        *,
        usernames: list[str],
        last_tweet_ids: Dict[str, str],
        initialized_usernames: Dict[str, bool],
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
                        initialized_usernames[username] = row.initialized
                    else:
                        last_tweet_ids[username] = "0"
                        initialized_usernames[username] = False

    async def persist(
        self,
        username: str,
        *,
        last_tweet_ids: Dict[str, str],
        initialized_usernames: Dict[str, bool],
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

    async def delete(self, username: str) -> None:
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XMonitorState, username)
                if row:
                    await session.delete(row)
