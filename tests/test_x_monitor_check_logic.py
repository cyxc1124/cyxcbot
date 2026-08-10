"""Minimal tests for X monitor check_logic."""

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
    # check_logic imports utils.x_api.models
    _ensure_package("utils", ROOT / "utils")
    _ensure_package("utils.x_api", ROOT / "utils" / "x_api")
    _load_module("utils.x_api.models", ROOT / "utils" / "x_api" / "models.py")

    plugin_root = ROOT / "plugins" / "x_monitor"
    _ensure_package("plugins", ROOT / "plugins")
    _ensure_package("plugins.x_monitor", plugin_root)
    return _load_module(
        "plugins.x_monitor.check_logic",
        plugin_root / "check_logic.py",
    )


def _tweet(tweet_id: str):
    return SimpleNamespace(id=tweet_id)


def test_collect_new_tweets_filters_by_last_id():
    check_logic = _load_check_logic()
    tweets = [_tweet("1"), _tweet("5"), _tweet("3")]
    assert [t.id for t in check_logic.collect_new_tweets(tweets, "3")] == ["5"]


def test_collect_new_tweets_compares_as_int():
    check_logic = _load_check_logic()
    tweets = [_tweet("9"), _tweet("10")]
    assert [t.id for t in check_logic.collect_new_tweets(tweets, "9")] == ["10"]


def test_compute_first_baseline_last_id_empty():
    check_logic = _load_check_logic()
    assert check_logic.compute_first_baseline_last_id([]) is None


def test_compute_first_baseline_last_id_returns_max():
    check_logic = _load_check_logic()
    tweets = [_tweet("10"), _tweet("42"), _tweet("7")]
    assert check_logic.compute_first_baseline_last_id(tweets) == "42"


def test_should_initialize_after_first_poll_requires_baseline():
    check_logic = _load_check_logic()
    assert check_logic.should_initialize_after_first_poll(None) is False
    assert check_logic.should_initialize_after_first_poll("42") is True


def test_should_fill_display_name_only_when_empty():
    check_logic = _load_check_logic()
    assert check_logic.should_fill_display_name(None) is True
    assert check_logic.should_fill_display_name("") is True
    assert check_logic.should_fill_display_name("  ") is True
    assert check_logic.should_fill_display_name("手动名称") is False
