"""Tests for X API timeline query params (since_id)."""

from __future__ import annotations

from utils.x_api.client import build_user_timeline_params


def test_build_params_without_since_id():
    params = build_user_timeline_params(max_results=5)
    assert params["max_results"] == "5"
    assert params["exclude"] == "retweets,replies"
    assert "since_id" not in params


def test_build_params_with_since_id():
    params = build_user_timeline_params(max_results=10, since_id="1234567890")
    assert params["max_results"] == "10"
    assert params["since_id"] == "1234567890"


def test_build_params_ignores_zero_since_id():
    params = build_user_timeline_params(since_id="0")
    assert "since_id" not in params
    params = build_user_timeline_params(since_id="")
    assert "since_id" not in params
    params = build_user_timeline_params(since_id=None)
    assert "since_id" not in params


def test_build_params_clamps_max_results():
    assert build_user_timeline_params(max_results=1)["max_results"] == "5"
    assert build_user_timeline_params(max_results=500)["max_results"] == "100"
