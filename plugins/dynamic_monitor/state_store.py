"""动态监控运行时状态的 DB 持久化。"""

import json
from typing import Callable, Dict, Optional

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import DynamicMonitorState
from shared.notify.delivery import PendingDelivery


class DynamicMonitorStateStore:
    """负责 DynamicMonitor 运行时状态的加载、持久化与删除。"""

    async def load(
        self,
        *,
        uids: list[str],
        last_dynamic_ids: Dict[str, int],
        initialized_uids: Dict[str, bool],
        pinned_dynamic_ids: Dict[str, Optional[int]],
        pending_targets: dict[tuple[str, int | str, bool], PendingDelivery]
        | None = None,
    ) -> None:
        for uid in uids:
            if uid not in pinned_dynamic_ids:
                pinned_dynamic_ids[uid] = None

        if not uids:
            return

        async with get_session() as session:
            async with session.begin():
                rows = (
                    await session.scalars(
                        select(DynamicMonitorState).where(
                            DynamicMonitorState.uid.in_(uids)
                        )
                    )
                ).all()
                by_uid = {row.uid: row for row in rows}

                for uid in uids:
                    if pending_targets is not None:
                        for key in [key for key in pending_targets if key[0] == uid]:
                            pending_targets.pop(key)
                    row = by_uid.get(uid)
                    if row:
                        last_dynamic_ids[uid] = row.last_dynamic_id
                        initialized_uids[uid] = row.initialized
                        pinned_dynamic_ids[uid] = row.pinned_dynamic_id
                        if pending_targets is not None:
                            for data in json.loads(row.pending_deliveries or "[]"):
                                key = (uid, data["dynamic_id"], data["is_pinned"])
                                pending_targets[key] = PendingDelivery.from_data(data)
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
        pending_targets: dict[tuple[str, int | str, bool], PendingDelivery]
        | None = None,
        check_still_valid: Optional[Callable[[], bool]] = None,
    ) -> None:
        if check_still_valid is not None and not check_still_valid():
            return
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DynamicMonitorState, uid)
                if check_still_valid is not None and not check_still_valid():
                    return
                if not row:
                    row = DynamicMonitorState(uid=uid)
                    session.add(row)
                row.last_dynamic_id = last_dynamic_ids.get(uid, 0)
                row.initialized = initialized_uids.get(uid, False)
                row.pinned_dynamic_id = pinned_dynamic_ids.get(uid)
                if pending_targets is not None:
                    row.pending_deliveries = json.dumps(
                        [
                            {
                                "dynamic_id": key[1],
                                "is_pinned": key[2],
                                **pending.to_data(),
                            }
                            for key, pending in pending_targets.items()
                            if key[0] == uid
                        ],
                        ensure_ascii=False,
                    )

    async def delete(self, uid: str) -> None:
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DynamicMonitorState, uid)
                if row:
                    await session.delete(row)
