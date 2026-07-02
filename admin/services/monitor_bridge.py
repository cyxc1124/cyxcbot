"""Bridge to plugin monitor instances (only admin module may import plugins)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from nonebot.log import logger

from shared.config.service import get_config_service
from shared.monitor.poll_schedule import (
    compute_dynamic_poll_schedule,
    compute_live_poll_schedule,
)


def get_dynamic_monitor_instance():
    from plugins.dynamic_monitor.dynamic_monitor import dynamic_monitor_instance

    return dynamic_monitor_instance


def get_live_monitor_instance():
    from plugins.live_monitor.live_monitor import live_monitor_instance

    return live_monitor_instance


async def reload_dynamic_monitor() -> bool:
    from plugins.dynamic_monitor import dynamic_monitor as dynamic_monitor_mod

    snap = get_config_service().get_snapshot()
    has_targets = bool(snap.dynamic_monitor_mapping)
    instance_before = dynamic_monitor_mod.dynamic_monitor_instance

    if instance_before is None and not has_targets:
        return False

    try:
        await dynamic_monitor_mod.sync_from_config_reload(snap)
    except Exception:
        logger.opt(exception=True).error("动态监控热重载失败")
        return False

    instance_after = dynamic_monitor_mod.dynamic_monitor_instance
    if instance_before is None and instance_after is not None:
        logger.info("动态监控已从空配置状态启动")
    elif instance_before is not None and instance_after is None:
        logger.info("动态监控目标已清空，监控已停止")

    return True


async def reload_live_monitor() -> bool:
    from plugins.live_monitor import live_monitor as live_monitor_mod

    snap = get_config_service().get_snapshot()
    has_targets = bool(snap.live_monitor_mapping)
    instance_before = live_monitor_mod.live_monitor_instance

    if instance_before is None and not has_targets:
        return False

    try:
        await live_monitor_mod.sync_from_config_reload(snap)
    except Exception:
        logger.opt(exception=True).error("直播监控热重载失败")
        return False

    instance_after = live_monitor_mod.live_monitor_instance
    if instance_before is None and instance_after is not None:
        logger.info("直播监控已从空配置状态启动")
    elif instance_before is not None and instance_after is None:
        logger.info("直播监控目标已清空，监控已停止")

    return True


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

    if room_id:
        results = []
        try:
            detail = await instance.check_room_now(room_id)
            if detail:
                results.append(detail)
        except Exception:
            logger.opt(exception=True).error("直播间 {} 手动检查失败", room_id)
            return {"success": False, "message": f"Check failed for room {room_id}"}
        return {
            "success": True,
            "message": f"Checked {len(results)} room(s)",
            "result": {"rooms": results},
        }

    outcome = await instance.run_manual_check(room_ids)
    checked = outcome["checked"]
    failed = outcome["failed"]
    results = [{"room_id": rid, "checked": True} for rid in checked]

    if not checked and failed:
        return {
            "success": False,
            "message": f"All {len(failed)} check(s) failed",
            "result": {"rooms": results, "failed_room_ids": failed},
        }

    message = f"Checked {len(checked)} room(s)"
    if failed:
        message += f", {len(failed)} failed"

    return {
        "success": True,
        "message": message,
        "result": {"rooms": results, "failed_room_ids": failed},
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
        "dynamic_checks_total": dynamic.checks_total if dynamic else 0,
        "live_checks_total": live.checks_total if live else 0,
        "dynamic_new_dynamics_total": dynamic.new_dynamics_total if dynamic else 0,
    }


def build_dynamic_monitor_status() -> Dict[str, Any]:
    status = get_monitor_status()
    instance = get_dynamic_monitor_instance()
    snap = get_config_service().get_snapshot()
    target_count = len(snap.dynamic_monitor_mapping)
    poll_schedule = compute_dynamic_poll_schedule(
        target_count,
        snap.dynamic_monitor_interval,
        use_stagger=snap.dynamic_monitor_use_stagger,
    )
    return {
        "enabled": status["dynamic_running"],
        "interval_seconds": snap.dynamic_monitor_interval,
        "target_count": target_count,
        "poll_schedule": poll_schedule,
        "last_check_at": instance.last_check_at if instance else None,
        "last_fetch_at": None,
        "last_error": None,
        "checks_total": instance.checks_total if instance else 0,
        "new_dynamics_total": instance.new_dynamics_total if instance else 0,
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
        "checks_total": instance.checks_total if instance else 0,
        "targets": targets,
    }


def get_system_monitor_status() -> Dict[str, Any]:
    from shared.monitor.system_metrics import build_system_metrics_payload

    return build_system_metrics_payload()


def get_dynamic_monitor_details() -> List[Dict[str, Any]]:
    instance = get_dynamic_monitor_instance()
    snap = get_config_service().get_snapshot()
    details = []
    for uid in snap.dynamic_monitor_mapping:
        details.append(
            {
                "uid": uid,
                "last_dynamic_id": instance.last_dynamic_ids.get(uid, 0)
                if instance
                else 0,
                "initialized": instance.initialized_uids.get(uid, False)
                if instance
                else False,
                "pinned_dynamic_id": instance.pinned_dynamic_ids.get(uid)
                if instance
                else None,
                "group_count": len(snap.dynamic_monitor_mapping.get(uid, [])),
                "user_count": len(snap.dynamic_monitor_user_mapping.get(uid, [])),
            }
        )
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
        details.append(
            {
                "room_id": room_id,
                "previous_status": state.previous_status.name
                if state and state.previous_status
                else None,
                "streamer_name": state.user_info.name
                if state and state.user_info
                else None,
                "is_living": is_living,
                "group_count": len(snap.live_monitor_mapping.get(room_id, [])),
                "user_count": len(snap.live_monitor_user_mapping.get(room_id, [])),
            }
        )
    return details
