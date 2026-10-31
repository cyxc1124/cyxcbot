"""Douyin API client: 403 retry and Cookie header."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from utils.douyin_api.client import (
    DouyinAPIClient,
    _gateway_error_snippet,
    _should_retry_http_status,
)
from utils.douyin_api.cookie_utils import (
    cookie_header,
    cookie_value,
    cookies_from_http_response,
)


def test_should_retry_http_status():
    assert _should_retry_http_status(403)
    assert _should_retry_http_status(429)
    assert _should_retry_http_status(503)
    assert not _should_retry_http_status(200)
    assert not _should_retry_http_status(400)
    assert not _should_retry_http_status(404)


def test_cookie_value_is_case_insensitive():
    assert cookie_value({"UIFID": "abc"}, "uifid") == "abc"
    assert cookie_value({"uifid": "xyz"}, "UIFID") == "xyz"
    assert cookie_value({"ttwid": "1"}, "UIFID", "uifid") == ""


@pytest.mark.parametrize("reason", ["Uifid Not Found", "Signature Not Found"])
def test_argus_gateway_snippet_only_returns_known_reason(reason):
    expected = f"Blocked by ArgusSecurityPlugin {reason}"
    assert _gateway_error_snippet(expected) == expected
    assert (
        _gateway_error_snippet(f"  Blocked\nby ArgusSecurityPlugin {reason}\r\n")
        == expected
    )
    assert _gateway_error_snippet(f"{expected} sessionid=dummy-secret") == expected


@pytest.mark.parametrize(
    "body",
    [
        "",
        "sessionid=dummy-cookie",
        "https://www.douyin.com/?msToken=dummy-token",
        "Uifid Not Found sessionid=dummy-cookie",
        "Signature Not Found msToken=dummy-token",
    ],
)
def test_gateway_snippet_drops_unknown_response_body(body):
    assert _gateway_error_snippet(body) == ""


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
        self.content = aiohttp.StreamReader(Mock(_reading_paused=False), limit=2**16)
        self.content.feed_data(body)
        self.content.feed_eof()

    async def read(self) -> bytes:
        return self._body

    async def json(self, content_type=None):
        return json.loads(self._body)

    async def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_default_query_uses_cookie_uifid_and_omits_empty():
    client = DouyinAPIClient({"UIFID": "from-cookie", "s_v_web_id": "verify_x"})
    with patch.object(client, "_ensure_ms_token", new=AsyncMock(return_value="tok")):
        query = await client._default_query()
    assert query["uifid"] == "from-cookie"
    assert query["verifyFp"] == "verify_x"
    assert query["fp"] == "verify_x"
    assert query["msToken"] == "tok"

    guest = DouyinAPIClient({})
    with patch.object(guest, "_ensure_ms_token", new=AsyncMock(return_value="tok")):
        empty = await guest._default_query()
    assert "uifid" not in empty
    assert "verifyFp" not in empty


@pytest.mark.asyncio
async def test_request_json_sends_uifid_header():
    client = DouyinAPIClient({"UIFID": "from-cookie", "ttwid": "1"})
    captured: list[dict] = []

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            captured.append(kwargs)
            return _FakeResp(200, b'{"ok": true}')

    client._session = _FakeSession()
    data = await client._request_json("/aweme/v1/web/aweme/detail/", {"aweme_id": "1"})
    assert data == {"ok": True}
    assert captured[0]["headers"]["uifid"] == "from-cookie"
    assert captured[0]["headers"]["x-tt-argus"] == "1"


@pytest.mark.asyncio
async def test_request_json_omits_argus_headers_without_uifid():
    client = DouyinAPIClient({"ttwid": "1"})
    captured: list[dict] = []

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            captured.append(kwargs)
            return _FakeResp(200, b'{"ok": true}')

    client._session = _FakeSession()
    data = await client._request_json("/aweme/v1/web/aweme/detail/", {"aweme_id": "1"})
    assert data == {"ok": True}
    assert "uifid" not in captured[0]["headers"]
    assert "x-tt-argus" not in captured[0]["headers"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["Uifid Not Found", "Signature Not Found"])
@pytest.mark.parametrize("suffix", ["", " sessionid=dummy-secret"])
async def test_request_json_does_not_retry_argus_missing(reason, suffix):
    client = DouyinAPIClient({"ttwid": "1"})
    calls = {"n": 0}

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            calls["n"] += 1
            return _FakeResp(
                403, f"Blocked by ArgusSecurityPlugin {reason}{suffix}".encode()
            )

    client._session = _FakeSession()
    with (
        patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("utils.douyin_api.client.logger") as log,
    ):
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}
        )
    assert data == {}
    assert calls["n"] == 1
    sleep.assert_not_called()
    assert "dummy-secret" not in str(log.mock_calls)
    log.error.assert_called_once_with(
        "抖音 API 网关拒绝 path={} status={} reason={}",
        "/aweme/v1/web/aweme/detail/",
        403,
        f"Blocked by ArgusSecurityPlugin {reason}",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429, 503])
@pytest.mark.parametrize(
    ("chunks", "retry"),
    [
        ((b"Gateway unavailable",), True),
        ((b"Blocked by Ar",), True),
        ((b"Blocked by Ar", b"gusSecurityPlugin Uifid ", b"Not Found"), False),
        ((b"Blocked by ArgusSecurityPlugin Signature Not Found",), False),
    ],
    ids=["unknown", "partial-argus", "uifid", "signature"],
)
async def test_request_json_handles_short_error_prefix_without_eof(
    status, chunks, retry
):
    client = DouyinAPIClient({"ttwid": "1"})
    response = _FakeResp(status, b"")
    response.content = aiohttp.StreamReader(Mock(_reading_paused=False), limit=2**16)
    for chunk in chunks:
        response.content.feed_data(chunk)
    queue = [response, _FakeResp(200, b'{"ok": true}')]
    calls = {"n": 0}

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            calls["n"] += 1
            return queue.pop(0)

    client._session = _FakeSession()
    with patch(
        "utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        data = await asyncio.wait_for(
            client._request_json("/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}),
            timeout=1,
        )
    assert data == ({"ok": True} if retry else {})
    assert calls["n"] == (2 if retry else 1)
    if retry:
        sleep.assert_awaited_once()
    else:
        sleep.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 503])
async def test_request_json_only_reads_bounded_error_prefix(status):
    client = DouyinAPIClient({"ttwid": "1"})
    body = b"x" * 1024 * 1024
    response = _FakeResp(status, body)
    response.read = AsyncMock(side_effect=AssertionError("full response read"))
    response.text = AsyncMock(side_effect=AssertionError("full response text"))
    queue = [response, _FakeResp(200, b'{"ok": true}')]

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            return queue.pop(0)

    client._session = _FakeSession()
    with patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock):
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}
        )
    assert data == {"ok": True}
    assert response.content.read_nowait() == body[512:]
    response.read.assert_not_called()
    response.text.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429, 503])
async def test_request_json_retries_when_error_body_never_arrives(status):
    client = DouyinAPIClient({"ttwid": "1"})
    responses = []
    for _ in range(2):
        response = _FakeResp(status, b"")
        response.content = aiohttp.StreamReader(
            Mock(_reading_paused=False), limit=2**16
        )
        responses.append(response)
    queue = [*responses, _FakeResp(200, b'{"ok": true}')]

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            return queue.pop(0)

    client._session = _FakeSession()
    with (
        patch("utils.douyin_api.client._GATEWAY_ERROR_READ_TIMEOUT", 0.01),
        patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        data = await asyncio.wait_for(
            client._request_json("/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}),
            timeout=1,
        )
    assert data == {"ok": True}
    assert not queue
    assert sleep.await_count == 2
    assert all(not response.content.at_eof() for response in responses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "secret"),
    [
        (b"Cookie: sessionid=dummy-cookie", "dummy-cookie"),
        (b"https://www.douyin.com/?msToken=dummy-token", "dummy-token"),
        (b"Uifid Not Found sessionid=dummy-cookie", "dummy-cookie"),
    ],
)
async def test_request_json_retries_unknown_gateway_body_without_logging_secret(
    body, secret
):
    client = DouyinAPIClient({"ttwid": "1"})
    calls = {"n": 0}

    class _FakeSession:
        closed = False

        def get(self, url, **kwargs):
            calls["n"] += 1
            return _FakeResp(403, body)

    client._session = _FakeSession()
    with (
        patch("utils.douyin_api.client.asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("utils.douyin_api.client.logger") as log,
    ):
        data = await client._request_json(
            "/aweme/v1/web/aweme/detail/", {"aweme_id": "1"}, max_retries=2
        )
    assert data == {}
    assert calls["n"] == 2
    sleep.assert_awaited_once()
    assert secret not in str(log.mock_calls)
    assert log.warning.call_count == 2


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
