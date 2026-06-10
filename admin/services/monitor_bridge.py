"""Bridge to plugin monitor instances (only admin module may import plugins)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from nonebot.log import logger

from shared.config.service import get_config_service
from shared.monitor.poll_schedule import compute_dynamic_poll_schedule, compute_live_poll_schedule


def get_dynamic_monitor_instance():
    from plugins.dynamic_monitor.dynamic_monitor import dynamic_monitor_instance

    return dynamic_monitor_instance


def get_live_monitor_instance():
    from plugins.live_monitor.live_monitor import live_monitor_instance

    return live_monitor_instance


async def reload_dynamic_monitor() -> bool:
    from plugins.dynamic_monitor.dynamic_monitor import (
        start_dynamic_monitor,
        stop_dynamic_monitor,
    )

    snap = get_config_service().get_snapshot()
    has_targets = bool(snap.dynamic_monitor_mapping)
    instance = get_dynamic_monitor_instance()

    if instance is None:
        if not has_targets:
            return False
        try:
            await start_dynamic_monitor()
            logger.info("动态监控已从空配置状态启动")
            return True
        except Exception as exc:
            logger.error(f"Failed to start dynamic monitor: {exc}")
            return False

    if not has_targets:
        try:
            await stop_dynamic_monitor()
            logger.info("动态监控目标已清空，监控已停止")
            return True
        except Exception as exc:
            logger.error(f"Failed to stop dynamic monitor: {exc}")
            return False

    try:
        await instance.reload_config()
        return True
    except Exception as exc:
        logger.error(f"Failed to reload dynamic monitor: {exc}")
        return False


async def reload_live_monitor() -> bool:
    from plugins.live_monitor.live_monitor import (
        start_live_monitor,
        stop_live_monitor,
    )

    snap = get_config_service().get_snapshot()
    has_targets = bool(snap.live_monitor_mapping)
    instance = get_live_monitor_instance()

    if instance is None:
        if not has_targets:
            return False
        try:
            await start_live_monitor()
            logger.info("直播监控已从空配置状态启动")
            return True
        except Exception as exc:
            logger.error(f"Failed to start live monitor: {exc}")
            return False

    if not has_targets:
        try:
            await stop_live_monitor()
            logger.info("直播监控目标已清空，监控已停止")
            return True
        except Exception as exc:
            logger.error(f"Failed to stop live monitor: {exc}")
            return False

    try:
        await instance.reload_config()
        return True
    except Exception as exc:
        logger.error(f"Failed to reload live monitor: {exc}")
        return False


async def reload_all_monitors() -> None:
    await reload_dynamic_monitor()
    await reload_live_monitor()


async def trigger_dynamic_check(uid: Optional[str] = None) -> Dict[str, Any]:
    instance = get_dynamic_monitor_instance()
    if not instance or not instance.is_running:
        return {"success": False, "message": "Dynamic monitor is not running"}

    snap = get_config_service().get_snapshot()
    uids = [uid] if uid else list(snap.dynamic_monitor_mapping.keys())
    if not uids:
        return {"success": False, "message": "No dynamic targets configured"}

    outcome = await instance.run_manual_check(uids)
    checked = outcome["checked"]
    failed = outcome["failed"]

    if not checked and failed:
        return {
            "success": False,
            "message": f"All {len(failed)} check(s) failed",
            "result": {"checked_uids": checked, "failed_uids": failed},
        }

    message = f"Checked {len(checked)} target(s)"
    if failed:
        message += f", {len(failed)} failed"

    return {
        "success": True,
        "message": message,
        "result": {"checked_uids": checked, "failed_uids": failed},
    }


async def trigger_live_check(room_id: Optional[str] = None) -> Dict[str, Any]:
    instance = get_live_monitor_instance()
    if not instance or not instance.is_running:
        return {"success": False, "message": "Live monitor is not running"}

    snap = get_config_service().get_snapshot()
    room_ids = [room_id] if room_id else list(snap.live_monitor_mapping.keys())
    if not room_ids:
        return {"success": False, "message": "No live targets configured"}

    results = []
    for rid in room_ids:
        try:
            if room_id:
                detail = await instance.check_room_now(rid)
                if detail:
                    results.append(detail)
            else:
                await instance._check_room_status(rid)
                results.append({"room_id": rid, "checked": True})
        except Exception as exc:
            logger.error(f"Manual live check failed for {rid}: {exc}")

    return {
        "success": True,
        "message": f"Checked {len(results)} room(s)",
        "result": {"rooms": results},
    }


def get_monitor_status() -> Dict[str, Any]:
    from shared.runtime import get_uptime_seconds

    dynamic = get_dynamic_monitor_instance()
    live = get_live_monitor_instance()
    snap = get_config_service().get_snapshot()
    dynamic_running = bool(dynamic and dynamic.is_running)
    live_running = bool(live and live.is_running)
    return {
        "running": True,
        "uptime_seconds": get_uptime_seconds(),
        "dynamic_running": dynamic_running,
        "live_running": live_running,
        "dynamic_target_count": len(snap.dynamic_monitor_mapping),
        "live_target_count": len(snap.live_monitor_mapping),
    }


def build_dynamic_monitor_status() -> Dict[str, Any]:
    status = get_monitor_status()
    instance = get_dynamic_monitor_instance()
    snap = get_config_service().get_snapshot()
    target_count = len(snap.dynamic_monitor_mapping)
    poll_schedule = compute_dynamic_poll_schedule(
        target_count,
        snap.dynamic_monitor_interval,
    )
    return {
        "enabled": status["dynamic_running"],
        "interval_seconds": snap.dynamic_monitor_interval,
        "target_count": target_count,
        "poll_schedule": poll_schedule,
        "last_check_at": instance.last_check_at if instance else None,
        "last_fetch_at": None,
        "last_error": None,
        "checks_total": 0,
        "new_dynamics_total": 0,
        "targets": get_dynamic_monitor_details(),
    }


def build_live_monitor_status() -> Dict[str, Any]:
    status = get_monitor_status()
    instance = get_live_monitor_instance()
    snap = get_config_service().get_snapshot()
    targets = get_live_monitor_details()
    live_rooms = sum(1 for t in targets if t.get("is_living"))
    target_count = len(snap.live_monitor_mapping)
    poll_schedule = compute_live_poll_schedule(
        target_count,
        snap.live_monitor_interval,
        use_websocket=snap.live_monitor_use_websocket,
    )
    return {
        "enabled": status["live_running"],
        "interval_seconds": snap.live_monitor_interval,
        "use_websocket": snap.live_monitor_use_websocket,
        "target_count": target_count,
        "poll_schedule": poll_schedule,
        "last_check_at": instance.last_check_at if instance else None,
        "last_error": None,
        "live_rooms": live_rooms,
        "checks_total": 0,
        "targets": targets,
    }


def get_system_monitor_status() -> Dict[str, Any]:
    import psutil

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": float(mem.percent),
        "memory_used_mb": mem.used / (1024 ** 2),
        "memory_total_mb": mem.total / (1024 ** 2),
        "disk_percent": float(disk.percent),
    }


def get_dynamic_monitor_details() -> List[Dict[str, Any]]:
    instance = get_dynamic_monitor_instance()
    snap = get_config_service().get_snapshot()
    details = []
    for uid in snap.dynamic_monitor_mapping:
        details.append({
            "uid": uid,
            "last_dynamic_id": instance.last_dynamic_ids.get(uid, 0) if instance else 0,
            "initialized": instance.initialized_uids.get(uid, False) if instance else False,
            "pinned_dynamic_id": instance.pinned_dynamic_ids.get(uid) if instance else None,
            "group_count": len(snap.dynamic_monitor_mapping.get(uid, [])),
            "user_count": len(snap.dynamic_monitor_user_mapping.get(uid, [])),
        })
    return details


def get_live_monitor_details() -> List[Dict[str, Any]]:
    instance = get_live_monitor_instance()
    snap = get_config_service().get_snapshot()
    details = []
    for room_id in snap.live_monitor_mapping:
        state = instance.room_states.get(room_id) if instance else None
        is_living = None
        if state and state.room_info:
            is_living = state.room_info.is_living()
        details.append({
            "room_id": room_id,
            "previous_status": state.previous_status.name if state and state.previous_status else None,
            "streamer_name": state.user_info.name if state and state.user_info else None,
            "is_living": is_living,
            "group_count": len(snap.live_monitor_mapping.get(room_id, [])),
            "user_count": len(snap.live_monitor_user_mapping.get(room_id, [])),
        })
    return details
