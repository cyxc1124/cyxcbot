"""动态监控运行时状态的 DB 持久化。"""

from typing import Callable, Dict, Optional

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import DynamicMonitorState


class DynamicMonitorStateStore:
    """负责 DynamicMonitor 运行时状态的加载、持久化与删除。"""

    async def load(
        self,
        *,
        uids: list[str],
        last_dynamic_ids: Dict[str, int],
        initialized_uids: Dict[str, bool],
        pinned_dynamic_ids: Dict[str, Optional[int]],
    ) -> None:
        for uid in uids:
            if uid not in pinned_dynamic_ids:
                pinned_dynamic_ids[uid] = None

        if not uids:
            return

        session = get_session()
        async with session.begin():
            rows = (
                await session.scalars(
                    select(DynamicMonitorState).where(DynamicMonitorState.uid.in_(uids))
                )
            ).all()
            by_uid = {row.uid: row for row in rows}

            for uid in uids:
                row = by_uid.get(uid)
                if row:
                    last_dynamic_ids[uid] = row.last_dynamic_id
                    initialized_uids[uid] = row.initialized
                    pinned_dynamic_ids[uid] = row.pinned_dynamic_id
                else:
                    last_dynamic_ids[uid] = 0
                    initialized_uids[uid] = False

    async def persist(
        self,
        uid: str,
        *,
        last_dynamic_ids: Dict[str, int],
        initialized_uids: Dict[str, bool],
        pinned_dynamic_ids: Dict[str, Optional[int]],
        check_still_valid: Optional[Callable[[], bool]] = None,
    ) -> None:
        if check_still_valid is not None and not check_still_valid():
            return
        session = get_session()
        async with session.begin():
            row = await session.get(DynamicMonitorState, uid)
            if not row:
                row = DynamicMonitorState(uid=uid)
                session.add(row)
            row.last_dynamic_id = last_dynamic_ids.get(uid, 0)
            row.initialized = initialized_uids.get(uid, False)
            row.pinned_dynamic_id = pinned_dynamic_ids.get(uid)

    async def delete(self, uid: str) -> None:
        session = get_session()
        async with session.begin():
            row = await session.get(DynamicMonitorState, uid)
            if row:
                await session.delete(row)
