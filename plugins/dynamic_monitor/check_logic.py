"""动态监控检查阶段的纯状态转换逻辑（可单测）。"""

from typing import Any, List, Optional, Sequence


def collect_new_dynamics(
    dynamics: Sequence[Any],
    last_dynamic_id: int,
) -> List[Any]:
    """收集 ID 大于 last_dynamic_id 的新动态。"""
    return [dynamic for dynamic in dynamics if dynamic.id > last_dynamic_id]


def compute_first_baseline_last_id(
    dynamics: Sequence[Any],
) -> Optional[int]:
    """首次基准记录时写入的 last_dynamic_id；无动态时返回 None。"""
    if not dynamics:
        return None
    return max(d.id for d in dynamics)


def should_notify_pinned_change(
    new_pinned_id: Optional[int],
    current_pinned_id: Optional[int],
) -> bool:
    """非首次启动时，当前与新的置顶 ID 均存在且发生变化时需要推送。"""
    return bool(new_pinned_id and current_pinned_id is not None)


def find_pinned_dynamic(
    dynamics: Sequence[Any],
    pinned_id: int,
) -> Optional[Any]:
    """在动态列表中查找指定置顶动态。"""
    return next((d for d in dynamics if d.id == pinned_id), None)
