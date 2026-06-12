"""Helpers for summarizing periodic monitor check logs."""

from __future__ import annotations

from typing import List

from nonebot.log import logger

SUCCESS_HEARTBEAT_CYCLES = 10


class CheckCycleLogger:
    """Accumulate per-target check results and emit one summary per cycle."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._checked = 0
        self._failures: List[str] = []
        self._success_cycles = 0

    def record_success(self) -> None:
        self._checked += 1

    def record_failure(self, target_id: str) -> None:
        self._checked += 1
        self._failures.append(target_id)

    def record_error(self, target_id: str, exc: Exception) -> None:
        self._checked += 1
        self._failures.append(target_id)
        logger.error(f"{self.label}检查 {target_id} 失败: {exc}")

    @property
    def checked_count(self) -> int:
        return self._checked

    @property
    def failure_ids(self) -> List[str]:
        return list(self._failures)

    def emit_summary(self, *, log_success_at_info: bool = False) -> None:
        if self._checked <= 0:
            self.reset()
            return

        if self._failures:
            logger.warning(
                f"{self.label}本轮检查完成: {self._checked} 个目标, "
                f"{len(self._failures)} 个失败 ({', '.join(self._failures)})"
            )
            self._success_cycles = 0
        else:
            message = f"{self.label}本轮检查完成: {self._checked} 个目标, 全部成功"
            if log_success_at_info:
                logger.info(message)
            else:
                logger.debug(message)
            self._success_cycles += 1
            if self._success_cycles % SUCCESS_HEARTBEAT_CYCLES == 0:
                logger.info(
                    f"{self.label}运行正常，已连续 {self._success_cycles} 轮检查全部成功"
                )
        self.reset()

    def reset(self) -> None:
        self._checked = 0
        self._failures.clear()
