"""直播监控运行时状态的 DB 持久化。"""

import asyncio
import json
from collections import defaultdict
from typing import Callable, Dict

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import LiveMonitorState
from shared.notify.delivery import PendingDelivery
from utils.bilibili_api import LiveStatus, RoomInfo, UserInfo

from .models import LiveRoomState


class LiveMonitorStateStore:
    """负责 LiveMonitor 运行时状态的加载、持久化与删除。"""

    def __init__(self):
        self._persist_locks = defaultdict(asyncio.Lock)

    async def load(
        self,
        room_states: Dict[str, LiveRoomState],
        room_ids: list[str],
    ) -> None:
        if not room_ids:
            return

        async with get_session() as session:
            async with session.begin():
                rows = (
                    await session.scalars(
                        select(LiveMonitorState).where(
                            LiveMonitorState.room_id.in_(room_ids)
                        )
                    )
                ).all()
                by_room_id = {row.room_id: row for row in rows}

                for room_id in room_ids:
                    row = by_room_id.get(room_id)
                    if row and room_id in room_states:
                        state = room_states[room_id]
                        if row.previous_status:
                            try:
                                state.previous_status = LiveStatus[row.previous_status]
                            except KeyError:
                                pass
                        if row.start_time:
                            state.start_time = row.start_time
                        data = json.loads(row.pending_notifications or "{}")
                        for status in ("start", "end"):
                            setattr(
                                state,
                                f"pending_{status}",
                                data.get(f"pending_{status}", False),
                            )
                            for kind in ("groups", "users"):
                                setattr(
                                    state,
                                    f"pending_{status}_{kind}",
                                    data.get(f"pending_{status}_{kind}", []),
                                )
                            delivery = data.get(f"pending_{status}_delivery")
                            setattr(
                                state,
                                f"pending_{status}_delivery",
                                PendingDelivery.from_data(delivery)
                                if delivery
                                else None,
                            )
                        room = data.get("last_live_room_info")
                        if room:
                            room["live_status"] = LiveStatus(room["live_status"])
                            state.last_live_room_info = RoomInfo(**room)
                        user = data.get("last_live_user_info")
                        if user:
                            state.last_live_user_info = UserInfo(**user)

    async def persist(
        self,
        room_id: str,
        state: LiveRoomState,
        *,
        check_still_valid: Callable[[], bool] | None = None,
    ) -> None:
        if check_still_valid is not None and not check_still_valid():
            return
        async with self._persist_locks[room_id]:
            async with get_session() as session:
                async with session.begin():
                    row = await session.get(LiveMonitorState, room_id)
                    if check_still_valid is not None and not check_still_valid():
                        return
                    if not row:
                        row = LiveMonitorState(room_id=room_id)
                        session.add(row)
                    row.previous_status = (
                        state.previous_status.name if state.previous_status else None
                    )
                    row.start_time = state.start_time or None
                    row.streamer_name = (
                        state.user_info.name if state.user_info else None
                    )
                    data = {}
                    if state.pending_start or state.pending_end:
                        for status in ("start", "end"):
                            for suffix in ("", "_groups", "_users"):
                                name = f"pending_{status}{suffix}"
                                data[name] = getattr(state, name)
                            delivery = getattr(state, f"pending_{status}_delivery")
                            data[f"pending_{status}_delivery"] = (
                                delivery.to_data() if delivery else None
                            )
                        data["last_live_room_info"] = (
                            state.last_live_room_info.to_dict()
                            if state.last_live_room_info
                            else None
                        )
                        data["last_live_user_info"] = (
                            state.last_live_user_info.to_dict()
                            if state.last_live_user_info
                            else None
                        )
                    row.pending_notifications = json.dumps(data, ensure_ascii=False)

    async def delete(self, room_id: str) -> None:
        async with get_session() as session:
            async with session.begin():
                row = await session.get(LiveMonitorState, room_id)
                if row:
                    await session.delete(row)
