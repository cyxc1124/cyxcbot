"""Tests for X monitor partial delivery retry helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from shared.notify.delivery import DeliveryResult, TargetDelivery

ROOT = Path(__file__).resolve().parents[1]


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


def _load_module(qualified_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(qualified_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _load_delivery_retry():
    _ensure_package("plugins", ROOT / "plugins")
    _ensure_package("plugins.x_monitor", ROOT / "plugins" / "x_monitor")
    return _load_module(
        "plugins.x_monitor.delivery_retry",
        ROOT / "plugins" / "x_monitor" / "delivery_retry.py",
    )


def test_failed_target_ids_splits_groups_and_users():
    delivery_retry = _load_delivery_retry()
    delivery = DeliveryResult(
        targets=[
            TargetDelivery("group", "1", True),
            TargetDelivery("group", "2", False, "boom"),
            TargetDelivery("user", "9", False, "gone"),
            TargetDelivery("user", "8", True),
        ]
    )
    assert delivery_retry.failed_target_ids(delivery) == (["2"], ["9"])


def test_encode_decode_pending_ids_roundtrip():
    delivery_retry = _load_delivery_retry()
    assert delivery_retry.encode_pending_ids(["1", "", "2"]) == "1,2"
    assert delivery_retry.decode_pending_ids("1,2") == ["1", "2"]
    assert delivery_retry.decode_pending_ids("") == []
    assert delivery_retry.decode_pending_ids(None) == []
