"""Tests for extracted live/dynamic monitor helper modules (issue #99)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_module(qualified_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(qualified_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    if name in sys.modules:
        module = sys.modules[name]
        if not getattr(module, "__path__", None):
            module.__path__ = [str(path)]
        return module
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load_check_logic():
    plugin_root = ROOT / "plugins" / "dynamic_monitor"
    _ensure_package("plugins", ROOT / "plugins")
    _ensure_package("plugins.dynamic_monitor", plugin_root)
    return _load_module(
        "plugins.dynamic_monitor.check_logic",
        plugin_root / "check_logic.py",
    )


def _load_notification_delivery():
    plugin_root = ROOT / "plugins" / "live_monitor"
    _ensure_package("plugins", ROOT / "plugins")
    _ensure_package("plugins.live_monitor", plugin_root)
    return _load_module(
        "plugins.live_monitor.notification_delivery",
        plugin_root / "notification_delivery.py",
    )


def _dynamic(dynamic_id: int, timestamp: int = 0):
    return SimpleNamespace(id=dynamic_id, timestamp=timestamp)


def test_collect_new_dynamics_filters_by_last_id():
    check_logic = _load_check_logic()
    dynamics = [_dynamic(1), _dynamic(5), _dynamic(3)]
    assert check_logic.collect_new_dynamics(dynamics, 3) == [_dynamic(5)]


def test_compute_first_baseline_last_id_empty():
    check_logic = _load_check_logic()
    assert check_logic.compute_first_baseline_last_id([]) is None


def test_compute_first_baseline_last_id_returns_max():
    check_logic = _load_check_logic()
    dynamics = [_dynamic(10), _dynamic(42), _dynamic(7)]
    assert check_logic.compute_first_baseline_last_id(dynamics) == 42


def test_should_notify_pinned_change_requires_both_ids():
    check_logic = _load_check_logic()
    assert check_logic.should_notify_pinned_change(99, None) is False
    assert check_logic.should_notify_pinned_change(None, 42) is False
    assert check_logic.should_notify_pinned_change(99, 42) is True


def test_find_pinned_dynamic():
    check_logic = _load_check_logic()
    dynamics = [_dynamic(1), _dynamic(2), _dynamic(3)]
    assert check_logic.find_pinned_dynamic(dynamics, 2) is dynamics[1]
    assert check_logic.find_pinned_dynamic(dynamics, 9) is None


def test_failed_target_ids_splits_groups_and_users():
    delivery_mod = _load_module(
        "shared.notify.delivery",
        ROOT / "shared" / "notify" / "delivery.py",
    )
    notification_delivery = _load_notification_delivery()
    delivery = delivery_mod.DeliveryResult(
        targets=[
            delivery_mod.TargetDelivery(
                target_type="group", target_id="1", success=True
            ),
            delivery_mod.TargetDelivery(
                target_type="group", target_id="2", success=False
            ),
            delivery_mod.TargetDelivery(
                target_type="user", target_id="9", success=False
            ),
        ],
    )
    assert notification_delivery.failed_target_ids(delivery) == (["2"], ["9"])
