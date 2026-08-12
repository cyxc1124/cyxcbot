"""X 监控 APScheduler 轮询任务注册。"""

from typing import Callable

from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

X_MONITOR_JOB_ID = "x_monitor_check"


def register_poll_job(
    *,
    use_stagger_poll: bool,
    username_count: int,
    monitor_interval: int,
    stagger_callback: Callable,
    batch_callback: Callable,
    schedule: dict,
) -> None:
    """注册或替换 X 监控轮询定时任务。"""
    if use_stagger_poll:
        tick = schedule["tick_interval_seconds"]
        callback = stagger_callback
        mode_label = "分散检查"
    else:
        tick = monitor_interval
        callback = batch_callback
        mode_label = "批量检查"

    scheduler.add_job(
        callback,
        "interval",
        seconds=tick,
        id=X_MONITOR_JOB_ID,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )
    logger.info(
        "X 监控调度({}): {} 个博主, "
        "定时 {:.1f}秒, "
        "每人周期约 {:.0f}秒, "
        "峰值约 {:.2f} 次/秒",
        mode_label,
        username_count,
        tick,
        schedule["per_target_cycle_seconds"],
        schedule["requests_per_second_peak"],
    )
    if schedule.get("warning"):
        logger.warning(schedule["warning"])


def remove_poll_job() -> None:
    """移除 X 监控轮询定时任务。"""
    try:
        scheduler.remove_job(X_MONITOR_JOB_ID)
        logger.info("X 监控定时任务已从调度器移除")
    except Exception:
        logger.opt(exception=True).warning("移除定时任务时出错")
