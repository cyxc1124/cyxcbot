"""截图服务须释放 Context、Browser 和 Playwright driver。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

import utils.screenshot.screenshot as ss
from shared.security import browser as browser_policy
from utils.bilibili_api.config import BilibiliConfig


def _runtime():
    context = SimpleNamespace(close=AsyncMock(), add_cookies=AsyncMock())
    browser = SimpleNamespace(
        close=AsyncMock(),
    )
    context.browser = browser
    playwright = SimpleNamespace(
        stop=AsyncMock(),
        chromium=SimpleNamespace(
            launch_persistent_context=AsyncMock(return_value=context)
        ),
    )
    manager = SimpleNamespace(
        start=AsyncMock(return_value=playwright), __aexit__=playwright.stop
    )
    return SimpleNamespace(
        context=context, browser=browser, playwright=playwright, manager=manager
    )


@pytest.fixture
def runtime(monkeypatch):
    runtime = _runtime()
    runtime.factory = MagicMock(return_value=runtime.manager)
    monkeypatch.setattr(ss, "async_playwright", runtime.factory)
    monkeypatch.setattr(ss, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(BilibiliConfig, "get_bilibili_cookie", lambda: "audit=value")
    monkeypatch.setattr(browser_policy, "_seed_profile", Mock(return_value=()))
    runtime.verify = AsyncMock()
    monkeypatch.setattr(browser_policy, "_verify_profile", runtime.verify)
    return runtime


def _assert_closed(runtime, context=1, browser=1, playwright=1):
    assert runtime.context.close.await_count == context
    assert runtime.browser.close.await_count == browser
    assert runtime.playwright.stop.await_count == playwright


async def test_close_releases_all_resources_once_in_reverse_order(runtime):
    calls = Mock()
    calls.attach_mock(runtime.context.close, "context")
    calls.attach_mock(runtime.browser.close, "browser")
    calls.attach_mock(runtime.playwright.stop, "playwright")
    shot = ss.DynamicScreenshot()

    assert await shot.init_browser()
    assert shot.browser_context is runtime.context
    await shot.close_browser()
    await shot.close_browser()

    assert shot.browser_context is None
    _assert_closed(runtime)
    assert [call[0] for call in calls.mock_calls] == [
        "context",
        "browser",
        "playwright",
    ]


async def test_reinitialize_releases_old_resources_before_replacing_them(runtime):
    replacement = _runtime()
    runtime.factory.side_effect = [runtime.manager, replacement.manager]
    shot = ss.DynamicScreenshot()

    assert await shot.init_browser()
    assert await shot.init_browser()

    _assert_closed(runtime)
    _assert_closed(replacement, context=0, browser=0, playwright=0)
    assert shot.browser_context is replacement.context
    await shot.close_browser()
    _assert_closed(replacement)


@pytest.mark.parametrize(
    ("stage", "closed"),
    [
        ("start", (0, 0, 1)),
        ("launch", (0, 0, 1)),
        ("verify", (1, 1, 1)),
        ("add_cookies", (1, 1, 1)),
    ],
)
@pytest.mark.parametrize("cancel", [False, True])
async def test_partial_initialization_releases_acquired_resources(
    runtime, stage, closed, cancel
):
    operation = {
        "start": runtime.manager.start,
        "launch": runtime.playwright.chromium.launch_persistent_context,
        "verify": runtime.verify,
        "add_cookies": runtime.context.add_cookies,
    }[stage]
    shot = ss.DynamicScreenshot()
    if cancel:
        started = asyncio.Event()

        async def wait_for_cancel(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        operation.side_effect = wait_for_cancel
        task = asyncio.create_task(shot.init_browser())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        operation.side_effect = RuntimeError("initialization failed")
        assert not await shot.init_browser()

    assert shot.browser_context is None
    _assert_closed(runtime, *closed)
    if stage in ("start", "launch", "verify"):
        runtime.context.add_cookies.assert_not_awaited()
    await shot.close_browser()
    _assert_closed(runtime, *closed)


@pytest.mark.parametrize("resource", ["context", "browser", "playwright"])
async def test_cleanup_failure_does_not_skip_remaining_resources(runtime, resource):
    operation = {
        "context": runtime.context.close,
        "browser": runtime.browser.close,
        "playwright": runtime.playwright.stop,
    }[resource]
    operation.side_effect = RuntimeError("cleanup failed")
    shot = ss.DynamicScreenshot()
    assert await shot.init_browser()

    await shot.close_browser()

    assert shot.browser_context is None
    _assert_closed(runtime)


async def test_close_during_initialization_waits_and_releases_resources(runtime):
    started = asyncio.Event()
    resume = asyncio.Event()

    async def start():
        started.set()
        await resume.wait()
        return runtime.playwright

    runtime.manager.start.side_effect = start
    shot = ss.DynamicScreenshot()
    init = asyncio.create_task(shot.init_browser())
    await started.wait()
    close = asyncio.create_task(shot.close_browser())
    await asyncio.sleep(0)
    assert not close.done()
    resume.set()
    assert await init
    await close

    assert shot.browser_context is None
    _assert_closed(runtime)
