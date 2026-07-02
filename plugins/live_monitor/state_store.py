"""直播监控运行时状态的 DB 持久化。"""

from typing import Dict

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.db.models import LiveMonitorState
from utils.bilibili_api import LiveStatus

from .models import LiveRoomState


class LiveMonitorStateStore:
    """负责 LiveMonitor 运行时状态的加载、持久化与删除。"""

    async def load(
        self,
        room_states: Dict[str, LiveRoomState],
        room_ids: list[str],
    ) -> None:
        if not room_ids:
            return

        session = get_session()
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

    async def persist(self, room_id: str, state: LiveRoomState) -> None:
        session = get_session()
        async with session.begin():
            row = await session.get(LiveMonitorState, room_id)
            if not row:
                row = LiveMonitorState(room_id=room_id)
                session.add(row)
            row.previous_status = (
                state.previous_status.name if state.previous_status else None
            )
            row.start_time = state.start_time or None
            row.streamer_name = state.user_info.name if state.user_info else None

    async def delete(self, room_id: str) -> None:
        session = get_session()
        async with session.begin():
            row = await session.get(LiveMonitorState, room_id)
            if row:
                await session.delete(row)
