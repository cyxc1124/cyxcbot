"""Douyin API client: 403 retry and Cookie header."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from utils.douyin_api.client import DouyinAPIClient, _should_retry_http_status
from utils.douyin_api.cookie_utils import cookie_header, cookies_from_http_response


def test_should_retry_http_status():
    assert _should_retry_http_status(403)
    assert _should_retry_http_status(429)
    assert _should_retry_http_status(503)
    assert not _should_retry_http_status(200)
    assert not _should_retry_http_status(400)
    assert not _should_retry_http_status(404)


def test_cookie_header_keeps_configured_pairs():
    assert (
        cookie_header({"ttwid": "a", "msToken": "b", "empty": "", "bad name": "x"})
        == "ttwid=a; msToken=b"
    )


def test_cookies_from_http_response_include_redirect_hops():
    hop = type("Hop", (), {"cookies": {"__ac_nonce": "n1"}})()
    final = type(
        "Resp",
        (),
        {"cookies": {"msToken": "tok"}, "history": (hop,)},
    )()
    assert cookies_from_http_response(final) == {
        "__ac_nonce": "n1",
        "msToken": "tok",
    }


class _FakeResp:
    def __init__(
        self,
        status: int,
        body: bytes,
        *,
        cookies: dict | None = None,
        history: tuple = (),
        url: str = "https://www.douyin.com/",
    ):
        self.status = status
        self._body = body
        self.cookies = cookies or {}
        self.history = history
        self.url = url

    async def read(self) -> bytes:
        return self._body

    async def json(self, content_type=None):
        return json.loads(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_request_json_retries_403_then_succeeds():
    client = DouyinAPIClient(
        {
            "ttwid": "1",
            "odin_tt": "2",
            "passport_csrf_token": "3",
            "sessionid": "sid",
        }
    )
    queue = [
        _FakeResp(403, b""),
        _FakeResp(200, b'{"aweme_detail": {"aweme_id": "9"}}'),
    ]
    captured: list[dict] = []

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            captured.append(kwargs)
            return queue.pop(0)

    client._session = _FakeSession()
    with patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock):
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/",
            {"aweme_id": "9"},
            max_retries=3,
        )
    assert data["aweme_detail"]["aweme_id"] == "9"
    assert len(captured) == 2
    cookie = captured[0]["headers"]["Cookie"]
    assert "ttwid=1" in cookie
    assert "sessionid=sid" in cookie
    assert "passport_csrf_token=3" in cookie


@pytest.mark.asyncio
async def test_request_json_does_not_retry_400():
    client = DouyinAPIClient({"ttwid": "1"})
    calls = {"n": 0}

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            calls["n"] += 1
            return _FakeResp(400, b"")

    client._session = _FakeSession()
    with patch(
        "utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}
        )
    assert data == {}
    assert calls["n"] == 1
    sleep.assert_not_called()


@pytest.mark.asyncio
async def test_request_json_keeps_set_cookie_across_403_retry():
    client = DouyinAPIClient({"ttwid": "1"})
    queue = [
        _FakeResp(403, b"", cookies={"msToken": "from-waf", "ttwid": "refreshed"}),
        _FakeResp(200, b'{"ok": true}'),
    ]
    captured: list[dict] = []

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            captured.append(kwargs)
            return queue.pop(0)

    client._session = _FakeSession()
    with patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock):
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/",
            {"aweme_id": "9"},
            max_retries=3,
        )
    assert data == {"ok": True}
    assert "msToken=from-waf" in captured[1]["headers"]["Cookie"]
    assert "ttwid=refreshed" in captured[1]["headers"]["Cookie"]


@pytest.mark.asyncio
async def test_short_url_set_cookie_is_sent_on_detail_request():
    client = DouyinAPIClient({"ttwid": "1"})
    captured: list[dict] = []

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            captured.append(kwargs)
            if "v.douyin.com" in str(url):
                return _FakeResp(
                    200,
                    b"",
                    cookies={"__ac_nonce": "abc"},
                    url="https://www.douyin.com/video/1",
                )
            return _FakeResp(200, b'{"aweme_detail": {"aweme_id": "1"}}')

    client._session = _FakeSession()
    final = await client.resolve_short_url("https://v.douyin.com/xxx/")
    assert final == "https://www.douyin.com/video/1"
    data = await client._request_json("/aweme/v1/web/aweme/detail/", {"aweme_id": "1"})
    assert data["aweme_detail"]["aweme_id"] == "1"
    assert "__ac_nonce=abc" in captured[1]["headers"]["Cookie"]
    assert "ttwid=1" in captured[1]["headers"]["Cookie"]
