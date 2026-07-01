"""Tests for Web Admin log websocket replay limits."""

from shared.logging.broadcast import MAX_BUFFER_CATCH_UP_PASSES, MAX_HANDOFF_PASSES


def test_catch_up_pass_limits_are_bounded() -> None:
    assert 1 <= MAX_BUFFER_CATCH_UP_PASSES <= 10
    assert 1 <= MAX_HANDOFF_PASSES <= 10
