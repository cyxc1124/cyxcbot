"""Shared polling / delivery plumbing for dynamic, live and X monitors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from nonebot.log import logger

from shared.monitor.background_task import spawn_background_task
from shared.monitor.check_cycle import CheckCycleLogger
from shared.monitor.concurrency import run_with_concurrency


class PollingMonitorMixin:
    """分散 / 批量 / 手动检查的公共实现。

    子类需设置 ``_monitor_label``，并实现 ``_target_ids`` 与 ``_check_target``
    （拉取失败返回 False）；``__init__`` 中需创建 ``is_running``、``last_check_at``、
    ``_stagger_index`` 与 ``_cycle_logger``。
    """

    _monitor_label = ""

    is_running: bool
    last_check_at: Optional[str]
    _stagger_index: int
    _cycle_logger: CheckCycleLogger

    def _target_ids(self) -> List[str]:
        raise NotImplementedError

    async def _check_target(self, target_id: str) -> bool:
        raise NotImplementedError

    def _touch_last_check_at(self) -> None:
        self.last_check_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    async def _check_next_target(self) -> None:
        """分散检查：每次 tick 只检查下一个目标，由 APScheduler 调用。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        target_ids = self._target_ids()
        if not target_ids:
            return

        if self._stagger_index >= len(target_ids):
            self._stagger_index = 0

        target_id = target_ids[self._stagger_index]
        self._stagger_index = (self._stagger_index + 1) % len(target_ids)
        cycle_completed = self._stagger_index == 0

        try:
            ok = await self._check_target(target_id)
            if ok is False:
                self._cycle_logger.record_failure(target_id)
            else:
                self._cycle_logger.record_success()
                self._touch_last_check_at()
        except Exception as e:
            self._cycle_logger.record_error(target_id, e)

        if cycle_completed:
            self._cycle_logger.emit_summary()
            self._touch_last_check_at()

    async def _check_all_targets(self) -> None:
        """批量检查全部目标，由 APScheduler 调用。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        target_ids = self._target_ids()
        if not target_ids:
            return

        try:
            results = await run_with_concurrency(target_ids, self._check_target)
            for target_id, ok in zip(target_ids, results):
                if isinstance(ok, BaseException):
                    self._cycle_logger.record_error(target_id, ok)
                elif ok is False:
                    self._cycle_logger.record_failure(target_id)
                else:
                    self._cycle_logger.record_success()

            self._cycle_logger.emit_summary()
            self._touch_last_check_at()
        except Exception:
            logger.opt(exception=True).error("{}检查出错", self._monitor_label)

    async def run_manual_check(
        self, target_ids: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """检查指定或全部目标（手动触发时使用）。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return {"checked": [], "failed": []}

        ids = target_ids if target_ids is not None else self._target_ids()
        cycle = CheckCycleLogger(f"{self._monitor_label}（手动）")
        checked: List[str] = []
        failed: List[str] = []

        try:
            results = await run_with_concurrency(ids, self._check_target)
            for target_id, ok in zip(ids, results):
                if isinstance(ok, BaseException):
                    cycle.record_error(target_id, ok)
                    failed.append(target_id)
                elif ok is False:
                    cycle.record_failure(target_id)
                    failed.append(target_id)
                else:
                    cycle.record_success()
                    checked.append(target_id)

            cycle.emit_summary(log_success_at_info=True)
            self._touch_last_check_at()
        except Exception:
            logger.opt(exception=True).error("{}检查出错", self._monitor_label)

        return {"checked": checked, "failed": failed}


class DeliveryGuardMixin:
    """check generation 防过期 + 后台投递任务管理（动态 / X 监控共用）。

    子类需实现 ``_is_active_target``，并在 ``__init__`` 中创建 ``_check_generation``
    与 ``_delivery_tasks``。
    """

    _delivery_task_name = "投递"

    _check_generation: Dict[str, int]
    _delivery_tasks: set[asyncio.Task]

    def _is_active_target(self, target_id: str) -> bool:
        raise NotImplementedError

    def _bump_check_generation(self, target_id: str) -> None:
        self._check_generation[target_id] = self._check_generation.get(target_id, 0) + 1

    def _check_still_valid(self, target_id: str, check_generation: int) -> bool:
        """fetch 后的异步阶段是否仍对应当前 generation（停用/重启用后应视为过期）。"""
        return self._is_active_target(target_id) and (
            self._check_generation.get(target_id, 0) == check_generation
        )

    def _spawn_delivery_task(self, coro, *, name: str | None = None) -> None:
        spawn_background_task(
            name or self._delivery_task_name, coro, tasks=self._delivery_tasks
        )

    async def _drain_pending_deliveries(self) -> None:
        """等待所有后台投递任务完成。"""
        while self._delivery_tasks:
            tasks = list(self._delivery_tasks)
            await asyncio.gather(*tasks, return_exceptions=True)
