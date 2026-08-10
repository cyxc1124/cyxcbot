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


def test_failed_targets_with_resume_parses_offset():
    delivery_retry = _load_delivery_retry()
    delivery = DeliveryResult(
        targets=[
            TargetDelivery("group", "1", False, "resume_from:2:timeout"),
            TargetDelivery("user", "9", False, "nope"),
        ]
    )
    assert delivery_retry.failed_targets_with_resume(delivery) == (
        [("1", 2)],
        [("9", 0)],
    )


def test_encode_decode_pending_ids_roundtrip():
    delivery_retry = _load_delivery_retry()
    assert delivery_retry.encode_pending_ids(["1", "", "2"]) == "1,2"
    assert delivery_retry.decode_pending_ids("1,2") == ["1", "2"]
    assert delivery_retry.decode_pending_ids("") == []
    assert delivery_retry.decode_pending_ids(None) == []


def test_encode_decode_pending_targets_with_resume():
    delivery_retry = _load_delivery_retry()
    encoded = delivery_retry.encode_pending_targets([("101", 0), ("102", 3)])
    assert encoded == "101,102@3"
    assert delivery_retry.decode_pending_targets(encoded) == [
        ("101", 0),
        ("102", 3),
    ]
    # 旧格式无 @offset 时视为从头重试
    assert delivery_retry.decode_pending_targets("101,102") == [
        ("101", 0),
        ("102", 0),
    ]


def test_normalize_batch_start_rejects_stale_offset():
    delivery_retry = _load_delivery_retry()
    ok, start, err = delivery_retry.normalize_batch_start(2, 2)
    assert ok is False
    assert start == 0
    assert err is not None and err.startswith("resume_from:0:stale_batches:")

    ok, start, err = delivery_retry.normalize_batch_start(5, 3)
    assert ok is False

    ok, start, err = delivery_retry.normalize_batch_start(1, 3)
    assert ok is True and start == 1 and err is None

    ok, start, err = delivery_retry.normalize_batch_start(0, 0)
    assert ok is True and start == 0


def test_normalize_batch_start_rejects_stale_plan():
    delivery_retry = _load_delivery_retry()
    ok, start, err = delivery_retry.normalize_batch_start(
        1,
        3,
        expected_fingerprint="v|i|v",
        actual_fingerprint="v|v|i",
    )
    assert ok is False
    assert start == 0
    assert err is not None and err.startswith("resume_from:0:stale_plan:")

    ok, start, err = delivery_retry.normalize_batch_start(
        1,
        3,
        expected_fingerprint="v|i|v",
        actual_fingerprint="v|i|v",
    )
    assert ok is True and start == 1 and err is None

    # 无 expected 时不校验指纹（首次 / 媒体未齐 pending）
    ok, start, err = delivery_retry.normalize_batch_start(
        1, 3, expected_fingerprint="", actual_fingerprint="v|i"
    )
    assert ok is True and start == 1


def test_batch_plan_fingerprint():
    delivery_retry = _load_delivery_retry()
    assert delivery_retry.batch_plan_fingerprint(["v", "i", "v"]) == "v|i|v"
    assert delivery_retry.batch_plan_fingerprint(["v", "i"], at_all=True) == "a|v|i"


def test_encode_decode_pending_tweet_ref():
    delivery_retry = _load_delivery_retry()
    assert delivery_retry.encode_pending_tweet_ref("123", "v|i") == "123#v|i"
    assert delivery_retry.decode_pending_tweet_ref("123#v|i") == ("123", "v|i")
    assert delivery_retry.decode_pending_tweet_ref("123") == ("123", "")
    assert delivery_retry.encode_pending_tweet_ref("123", "") == "123"
    # 指纹内 # 会被剥掉，避免破坏分隔
    assert delivery_retry.encode_pending_tweet_ref("1", "a#b") == "1#ab"
