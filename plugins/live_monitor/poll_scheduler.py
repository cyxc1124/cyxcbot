"""直播监控 APScheduler 轮询任务注册。"""

from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from shared.monitor.poll_schedule import LIVE_POLL_MISFIRE_GRACE_TIME_SECONDS

LIVE_MONITOR_JOB_ID = "live_monitor_check"


def register_poll_job(callback, poll_interval_seconds: int) -> None:
    """注册或替换直播监控轮询定时任务。"""
    scheduler.add_job(
        callback,
        "interval",
        seconds=poll_interval_seconds,
        id=LIVE_MONITOR_JOB_ID,
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=LIVE_POLL_MISFIRE_GRACE_TIME_SECONDS,
    )


def remove_poll_job() -> None:
    """移除直播监控轮询定时任务。"""
    try:
        scheduler.remove_job(LIVE_MONITOR_JOB_ID)
        logger.info("直播监控定时任务已移除")
    except Exception:
        logger.opt(exception=True).warning("移除定时任务时出错")
