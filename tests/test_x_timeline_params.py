"""Tests for X API timeline query params (since_id)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.x_api.client import XApiClient, build_user_timeline_params


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


def test_build_params_with_pagination_token():
    params = build_user_timeline_params(
        since_id="10",
        pagination_token="abc",
    )
    assert params["since_id"] == "10"
    assert params["pagination_token"] == "abc"


@pytest.mark.asyncio
async def test_fetch_user_tweets_aborts_on_mid_pagination_failure():
    client = XApiClient(session=MagicMock(), bearer="token")
    first_page = {
        "data": [{"id": "20", "text": "newer", "created_at": "2026-01-02T00:00:00Z"}],
        "meta": {"next_token": "page2"},
    }
    client._get_user_timeline_page = AsyncMock(side_effect=[first_page, None])

    result = await client.fetch_user_tweets(
        "42",
        since_id="10",
        username="demo",
        max_pages=5,
    )

    assert result is None
    assert client._get_user_timeline_page.await_count == 2
