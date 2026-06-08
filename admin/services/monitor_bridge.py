"""Bridge to plugin monitor instances (only admin module may import plugins)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from nonebot.log import logger

from shared.config.service import get_config_service


def get_dynamic_monitor_instance():
    from plugins.dynamic_monitor.dynamic_monitor import dynamic_monitor_instance

    return dynamic_monitor_instance


def get_live_monitor_instance():
    from plugins.live_monitor.live_monitor import live_monitor_instance

    return live_monitor_instance


async def reload_dynamic_monitor() -> bool:
    instance = get_dynamic_monitor_instance()
    if instance is None:
        return False
    try:
        await instance.reload_config()
        return True
    except Exception as exc:
        logger.error(f"Failed to reload dynamic monitor: {exc}")
        return False


async def reload_live_monitor() -> bool:
    instance = get_live_monitor_instance()
    if instance is None:
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

    checked = []
    for target_uid in uids:
        try:
            await instance._check_user_dynamic(target_uid)
            checked.append(target_uid)
        except Exception as exc:
            logger.error(f"Manual dynamic check failed for {target_uid}: {exc}")

    return {
        "success": True,
        "message": f"Checked {len(checked)} target(s)",
        "result": {"checked_uids": checked},
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
    dynamic = get_dynamic_monitor_instance()
    live = get_live_monitor_instance()
    snap = get_config_service().get_snapshot()
    return {
        "dynamic_running": bool(dynamic and dynamic.is_running),
        "live_running": bool(live and live.is_running),
        "dynamic_target_count": len(snap.dynamic_monitor_mapping),
        "live_target_count": len(snap.live_monitor_mapping),
    }


def get_system_monitor_status() -> Dict[str, Any]:
    import os
    import platform

    import psutil

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        import nonebot

        bot_version = nonebot.__version__
    except Exception:
        bot_version = os.getenv("GIT_TAG", "dev")

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": float(mem.percent),
        "memory_used_mb": mem.used / (1024 ** 2),
        "memory_total_mb": mem.total / (1024 ** 2),
        "disk_percent": float(disk.percent),
        "python_version": platform.python_version(),
        "bot_version": bot_version,
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
        })
    return details
