"""Unit tests for Douyin QR login helpers (no Playwright / network)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import shared.douyin.qrcode_login as qr_mod
from shared.douyin.qrcode_login import (
    QR_SELECTORS,
    DouyinQrcodeError,
    DouyinQrSession,
    close_qr_session,
    cookies_to_header,
    has_valid_login_cookie,
    is_logged_in_url,
    poll_qrcode_login,
    refresh_qrcode_login,
)


def test_qr_selectors_prefer_live_hashed_container():
    # Live panel: .XI37I0dP > img.RhjdbXj8[aria-label=二维码]
    assert QR_SELECTORS[0] == ".XI37I0dP img"
    assert "img.RhjdbXj8" in QR_SELECTORS
    assert ".XI37I0dP" in QR_SELECTORS
    assert any("二维码" in s for s in QR_SELECTORS)


@pytest.mark.asyncio
async def test_refresh_requires_existing_session():
    with pytest.raises(DouyinQrcodeError, match="缺少|不存在|过期"):
        await refresh_qrcode_login("")
    with pytest.raises(DouyinQrcodeError, match="不存在|过期"):
        await refresh_qrcode_login("no-such-session")


def test_cookies_to_header_and_sessionid_check():
    cookies = [
        {"name": "ttwid", "value": "a"},
        {"name": "sessionid", "value": "sid123"},
        {"name": "empty", "value": None},
    ]
    header = cookies_to_header(cookies)
    assert "ttwid=a" in header
    assert "sessionid=sid123" in header
    assert "empty=" not in header
    assert has_valid_login_cookie(cookies)
    assert not has_valid_login_cookie([{"name": "ttwid", "value": "a"}])


def test_is_logged_in_url():
    assert is_logged_in_url("https://www.douyin.com/")
    assert is_logged_in_url("https://www.douyin.com/user/self")
    assert is_logged_in_url("https://www.douyin.com/user/xxx")
    assert not is_logged_in_url("https://www.douyin.com/passport/login")
    assert not is_logged_in_url("https://example.com/")


def _make_fake_session(session_id: str = "abc123def456") -> DouyinQrSession:
    browser = MagicMock()
    browser.close = AsyncMock()
    playwright = MagicMock()
    playwright.stop = AsyncMock()
    page = MagicMock()
    page.url = "https://www.douyin.com/user/self"
    page.inner_text = AsyncMock(return_value="")
    context = MagicMock()
    context.cookies = AsyncMock(return_value=[])
    return DouyinQrSession(
        session_id=session_id,
        image_base64="old",
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
    )


@pytest.fixture
def isolated_qr_sessions(monkeypatch):
    """Isolate in-memory QR session maps for each test."""
    sessions: dict[str, DouyinQrSession] = {}
    deferred: dict[str, asyncio.Task] = {}
    monkeypatch.setattr(qr_mod, "_sessions", sessions)
    monkeypatch.setattr(qr_mod, "_deferred_close_tasks", deferred)
    monkeypatch.setattr(qr_mod, "_DEFERRED_CLOSE_SECONDS", 0.05)
    yield sessions, deferred
    for task in list(deferred.values()):
        task.cancel()


@pytest.mark.asyncio
async def test_poll_cancel_defers_close_then_reclaims_chromium(isolated_qr_sessions):
    """Tab close / client abort must not leave Chromium forever (PR #217 regression)."""
    sessions, deferred = isolated_qr_sessions
    session = _make_fake_session()
    sessions[session.session_id] = session

    task = asyncio.create_task(
        poll_qrcode_login(session.session_id, timeout_seconds=30)
    )
    # Allow poll to enter the sleep loop
    await asyncio.sleep(0)
    assert session.poll_active is True

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert session.session_id in sessions
    assert session.closed is False
    assert session.session_id in deferred

    await asyncio.sleep(0.12)
    assert session.session_id not in sessions
    assert session.closed is True
    session.browser.close.assert_awaited()
    session.playwright.stop.assert_awaited()


@pytest.mark.asyncio
async def test_refresh_claim_cancels_deferred_close_after_poll_abort(
    isolated_qr_sessions, monkeypatch
):
    """Refresh after abort must keep the same Playwright session alive."""
    sessions, deferred = isolated_qr_sessions
    session = _make_fake_session()
    sessions[session.session_id] = session

    task = asyncio.create_task(
        poll_qrcode_login(session.session_id, timeout_seconds=30)
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert session.session_id in deferred
    epoch_after_cancel = session.epoch

    async def fake_trigger(_page):
        return None

    async def fake_find(_page):
        element = MagicMock()
        element.screenshot = AsyncMock(return_value=b"png-bytes")
        return element

    fp_calls = {"n": 0}

    async def fingerprint_then_new(_page):
        fp_calls["n"] += 1
        # 第 1 次：old_fp；之后：新码指纹，走同页刷新成功路径
        return "fp-old" if fp_calls["n"] == 1 else "fp-new"

    monkeypatch.setattr(qr_mod, "_trigger_qr_refresh", fake_trigger)
    monkeypatch.setattr(qr_mod, "_qr_fingerprint", fingerprint_then_new)
    monkeypatch.setattr(qr_mod, "_find_qr_element", fake_find)

    result = await refresh_qrcode_login(session.session_id)
    assert result["session_id"] == session.session_id
    assert result["image_base64"]
    assert session.epoch > epoch_after_cancel
    assert session.session_id in sessions
    assert session.closed is False

    await asyncio.sleep(0.12)
    # Deferred close from abort must not fire after refresh claimed the session
    assert session.session_id in sessions
    assert session.closed is False
    await close_qr_session(session.session_id)


@pytest.mark.asyncio
async def test_poll_abort_after_refresh_claim_does_not_arm_deferred_close(
    isolated_qr_sessions, monkeypatch
):
    """Refresh claimed first: aborted poll must not schedule deferred on that epoch.

    Concrete trigger: user clicks refresh → frontend aborts poll while refresh API
    already bumped epoch. Buggy poll CancelledError used *current* epoch, so a
    slow refresh (goto fallback can exceed deferred delay) lost Chromium mid-flight.
    """
    sessions, deferred = isolated_qr_sessions
    session = _make_fake_session()
    sessions[session.session_id] = session

    entered = asyncio.Event()
    release = asyncio.Event()

    async def cookies_block():
        entered.set()
        await release.wait()
        return []

    session.context.cookies = AsyncMock(side_effect=cookies_block)
    session.page.wait_for_timeout = AsyncMock()
    session.page.goto = AsyncMock()

    poll_task = asyncio.create_task(
        poll_qrcode_login(session.session_id, timeout_seconds=30)
    )
    await entered.wait()
    epoch_during_poll = session.epoch
    assert session.poll_active is True

    refresh_hold = asyncio.Event()

    async def slow_trigger(_page):
        await refresh_hold.wait()

    monkeypatch.setattr(qr_mod, "_trigger_qr_refresh", slow_trigger)
    monkeypatch.setattr(qr_mod, "_qr_fingerprint", AsyncMock(return_value="fp-old"))
    monkeypatch.setattr(qr_mod, "_find_qr_element", AsyncMock(return_value=None))
    monkeypatch.setattr(qr_mod, "_wait_for_qr_element", AsyncMock(return_value=None))

    refresh_task = asyncio.create_task(refresh_qrcode_login(session.session_id))
    # refresh 先认领（bump epoch），再等 poll_active
    for _ in range(50):
        if session.epoch > epoch_during_poll:
            break
        await asyncio.sleep(0.01)
    assert session.epoch > epoch_during_poll

    poll_task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await poll_task

    # 修复后：不应再按 refresh 的 epoch 挂延迟关闭
    assert session.session_id not in deferred

    await asyncio.sleep(0.12)
    assert session.session_id in sessions
    assert session.closed is False

    assert session.poll_active is False

    refresh_hold.set()
    with pytest.raises(DouyinQrcodeError, match="刷新后未找到|重新获取"):
        await refresh_task
    # refresh 失败路径会自行挂上延迟清理，且旧 poll 不得留下 sticky poll_active
    assert session.poll_active is False
    assert session.session_id in deferred

    await asyncio.sleep(0.12)
    assert session.session_id not in sessions
    assert session.closed is True
    session.browser.close.assert_awaited()
