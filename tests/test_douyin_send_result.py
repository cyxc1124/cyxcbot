"""Tests for OneBot send success detection used by douyin link parser."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "plugins" / "douyin_link_parser" / "send_result.py"
_spec = importlib.util.spec_from_file_location("douyin_link_parser_send_result", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
is_onebot_send_success = _mod.is_onebot_send_success


def test_is_onebot_send_success():
    assert is_onebot_send_success({"message_id": 123})
    assert is_onebot_send_success({"message_id": "456"})
    assert is_onebot_send_success(42)
    # LuckyLilliaBot store.createMsgShortId: hash.readInt32BE() → signed int32
    assert is_onebot_send_success({"message_id": -904673447})
    assert is_onebot_send_success(-2146941368)
    assert not is_onebot_send_success(None)
    assert not is_onebot_send_success({})
    assert not is_onebot_send_success({"message_id": 0})
    assert not is_onebot_send_success(0)
    assert not is_onebot_send_success({"message_id": ""})
    assert not is_onebot_send_success({"status": "ok"})
