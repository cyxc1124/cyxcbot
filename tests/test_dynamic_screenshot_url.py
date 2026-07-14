"""Tests for dynamic push URL sync with screenshot page source."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.bilibili_api.dynamic_models import DynamicItem

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
PLUGIN_ROOT = PLUGINS_ROOT / "dynamic_monitor"


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


def _load_dynamic_monitor_module():
    _ensure_package("plugins", PLUGINS_ROOT)
    _ensure_package("plugins.dynamic_monitor", PLUGIN_ROOT)
    sys.modules.setdefault(
        "nonebot_plugin_apscheduler",
        MagicMock(scheduler=MagicMock()),
    )
    sys.modules.setdefault(
        "nonebot_plugin_orm",
        MagicMock(get_session=MagicMock()),
    )
    _load_module("plugins.dynamic_monitor.config", "config.py")
    _load_module("plugins.dynamic_monitor.sender", "sender.py")
    return _load_module("plugins.dynamic_monitor.dynamic_monitor", "dynamic_monitor.py")


def _load_module(qualified_name: str, filename: str):
    path = PLUGIN_ROOT / filename
    spec = importlib.util.spec_from_file_location(
        qualified_name,
        path,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


def _make_dynamic(
    dynamic_id: int = 1234567890,
    *,
    url: str | None = None,
    dynamic_type: int = 0,
) -> DynamicItem:
    item = DynamicItem(
        dynamic_id=dynamic_id,
        uid=1,
        name="tester",
        timestamp=1700000000,
        dynamic_type=dynamic_type,
    )
    if url is not None:
        item.url = url
    return item


@pytest.fixture
def dynamic_monitor_module():
    touched = {
        key: sys.modules.get(key)
        for key in (
            "plugins",
            "plugins.dynamic_monitor",
            "plugins.dynamic_monitor.config",
            "plugins.dynamic_monitor.sender",
            "plugins.dynamic_monitor.dynamic_monitor",
            "nonebot_plugin_apscheduler",
            "nonebot_plugin_orm",
            "utils.screenshot",
        )
    }
    screenshot_mock = MagicMock(
        init_screenshot_service=AsyncMock(),
        close_screenshot_service=AsyncMock(),
        get_dynamic_screenshot=AsyncMock(),
    )
    sys.modules["utils.screenshot"] = screenshot_mock
    try:
        module = _load_dynamic_monitor_module()
        yield module, screenshot_mock
    finally:
        for key, original in touched.items():
            if original is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


@pytest.mark.asyncio
async def test_fetch_dynamic_screenshot_syncs_opus_url(dynamic_monitor_module) -> None:
    monitor_mod, screenshot_mock = dynamic_monitor_module
    DynamicMonitor = monitor_mod.DynamicMonitor
    monitor = DynamicMonitor(SimpleNamespace(enable_screenshot=True))
    dynamic = _make_dynamic()
    opus_url = "https://www.bilibili.com/opus/1234567890"
    screenshot_mock.get_dynamic_screenshot.return_value = (b"png", None, opus_url)

    result = await monitor._fetch_dynamic_screenshot(dynamic)

    assert result == b"png"
    assert dynamic.url == opus_url


@pytest.mark.asyncio
async def test_fetch_dynamic_screenshot_syncs_t_bilibili_fallback(
    dynamic_monitor_module,
) -> None:
    monitor_mod, screenshot_mock = dynamic_monitor_module
    DynamicMonitor = monitor_mod.DynamicMonitor
    monitor = DynamicMonitor(SimpleNamespace(enable_screenshot=True))
    dynamic = _make_dynamic()
    t_url = "https://t.bilibili.com/1234567890"
    screenshot_mock.get_dynamic_screenshot.return_value = (b"png", None, t_url)

    await monitor._fetch_dynamic_screenshot(dynamic)

    assert dynamic.url == t_url


@pytest.mark.asyncio
async def test_fetch_dynamic_screenshot_keeps_video_url(dynamic_monitor_module) -> None:
    monitor_mod, screenshot_mock = dynamic_monitor_module
    DynamicMonitor = monitor_mod.DynamicMonitor
    monitor = DynamicMonitor(SimpleNamespace(enable_screenshot=True))
    video_url = "https://www.bilibili.com/video/BV1test"
    dynamic = _make_dynamic(url=video_url)
    screenshot_mock.get_dynamic_screenshot.return_value = (
        b"png",
        None,
        "https://www.bilibili.com/opus/1234567890",
    )

    await monitor._fetch_dynamic_screenshot(dynamic)

    assert dynamic.url == video_url


@pytest.mark.asyncio
async def test_fetch_dynamic_screenshot_skipped_when_disabled(
    dynamic_monitor_module,
) -> None:
    monitor_mod, screenshot_mock = dynamic_monitor_module
    DynamicMonitor = monitor_mod.DynamicMonitor
    monitor = DynamicMonitor(SimpleNamespace(enable_screenshot=False))
    dynamic = _make_dynamic()

    result = await monitor._fetch_dynamic_screenshot(dynamic)

    assert result is None
    screenshot_mock.get_dynamic_screenshot.assert_not_called()
    assert dynamic.url == "https://t.bilibili.com/1234567890"


def test_opus_first_child_title_is_ready() -> None:
    """带标题图文动态首子为 opus-module-title，应判定就绪、不 fallback（issue #119）。"""
    from utils.screenshot.screenshot import _opus_view_first_child_is_ready

    assert _opus_view_first_child_is_ready("opus-module-author")
    assert _opus_view_first_child_is_ready("opus-module-author other")
    assert _opus_view_first_child_is_ready("opus-module-title")
    assert not _opus_view_first_child_is_ready("opus-module-top")
    assert not _opus_view_first_child_is_ready("")  # 半加载：子节点未渲染


def test_dynamic_item_is_article() -> None:
    article = _make_dynamic(dynamic_type=DynamicItem.TYPE_ARTICLE)
    ordinary = _make_dynamic(dynamic_type=2)
    assert article.is_article
    assert not ordinary.is_article


@pytest.mark.asyncio
async def test_opus_page_ready_article_allows_module_top() -> None:
    """专栏首子常为 opus-module-top，不应因此判定未就绪。"""
    from utils.screenshot.screenshot import DynamicScreenshot

    page = AsyncMock()
    page.evaluate = AsyncMock(return_value="opus-module-top")
    shot = DynamicScreenshot()

    assert await shot._is_opus_page_ready(page, is_article=True) is True
    assert await shot._is_opus_page_ready(page, is_article=False) is False


@pytest.mark.asyncio
async def test_navigate_dynamic_page_passes_is_article() -> None:
    """导航应将 is_article 传给 opus 就绪检查。"""
    from utils.screenshot.screenshot import DynamicScreenshot

    page = AsyncMock()
    page.url = "https://www.bilibili.com/opus/1234567890"
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    card = MagicMock()
    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=True)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=card)
    shot._is_login_interstitial = AsyncMock(return_value=False)

    await shot._navigate_dynamic_page(page, 1234567890, is_article=True)

    shot._is_opus_page_ready.assert_awaited_with(page, is_article=True)


def test_is_dynamic_not_found_url() -> None:
    """不存在动态跳转链：opus 302→t.bilibili.com/0→www.bilibili.com/404（issue #119）。"""
    from utils.screenshot.screenshot import _is_dynamic_not_found_url

    assert _is_dynamic_not_found_url("https://t.bilibili.com/0")
    assert _is_dynamic_not_found_url("https://t.bilibili.com/0?from=feed")
    assert _is_dynamic_not_found_url("https://www.bilibili.com/404")
    # 占位 id（非真实动态）：含 404 或普通长 id 都不应被误判为不存在
    assert not _is_dynamic_not_found_url("https://t.bilibili.com/4040404040404040404")
    assert not _is_dynamic_not_found_url(
        "https://www.bilibili.com/opus/1234567890123456789"
    )


@pytest.mark.asyncio
async def test_navigate_dynamic_page_returns_post_navigation_url() -> None:
    from utils.screenshot.screenshot import DynamicScreenshot

    canonical_url = "https://www.bilibili.com/opus/1234567890?from=feed"
    page = AsyncMock()
    page.url = canonical_url
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    card = MagicMock()
    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=True)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=card)
    shot._is_login_interstitial = AsyncMock(return_value=False)

    result_card, page_url = await shot._navigate_dynamic_page(page, 1234567890)

    assert result_card is card
    assert page_url == canonical_url
    assert page_url != "https://www.bilibili.com/opus/1234567890"


@pytest.mark.asyncio
async def test_navigate_dynamic_page_genuine_404_raises_notfound() -> None:
    """两个候选 URL 都明确 404 时，判定动态不存在。"""
    from utils.screenshot.screenshot import DynamicScreenshot, Notfound

    page = AsyncMock()
    page.url = "https://www.bilibili.com/404"
    page.goto = AsyncMock(return_value=MagicMock(status=404))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=True)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=MagicMock())
    shot._is_login_interstitial = AsyncMock(return_value=False)

    with pytest.raises(Notfound):
        await shot._navigate_dynamic_page(page, 1234567890)


@pytest.mark.asyncio
async def test_navigate_dynamic_page_opus_redirect_to_zero_is_notfound() -> None:
    """opus 不存在时 302 到 t.bilibili.com/0（HTTP 200），应判定动态不存在（issue #119）。"""
    from utils.screenshot.screenshot import DynamicScreenshot, Notfound

    page = AsyncMock()
    page.url = "https://t.bilibili.com/0"
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=True)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=MagicMock())
    shot._is_login_interstitial = AsyncMock(return_value=False)

    with pytest.raises(Notfound):
        await shot._navigate_dynamic_page(page, 1234567890123456789)


@pytest.mark.asyncio
async def test_navigate_dynamic_page_unrendered_not_reported_as_notfound() -> None:
    """页面打开但内容未渲染（瞬时失败）时不能误报「动态不存在」（issue #119）。"""
    from utils.screenshot.screenshot import (
        DynamicScreenshot,
        Notfound,
        ScreenshotLoadError,
    )

    page = AsyncMock()
    page.url = "https://www.bilibili.com/opus/1234567890"
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=False)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=None)
    shot._is_login_interstitial = AsyncMock(return_value=False)

    with pytest.raises(ScreenshotLoadError) as exc_info:
        await shot._navigate_dynamic_page(page, 1234567890)
    assert not isinstance(exc_info.value, Notfound)


@pytest.mark.asyncio
async def test_navigate_dynamic_page_login_wall_not_reported_as_notfound() -> None:
    """命中登录墙属瞬时/可降级问题，动态仍可能存在，不能误报「动态不存在」。"""
    from utils.screenshot.screenshot import (
        DynamicScreenshot,
        Notfound,
        ScreenshotLoadError,
    )

    page = AsyncMock()
    page.url = "https://www.bilibili.com/opus/1234567890"
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=True)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=MagicMock())
    shot._is_login_interstitial = AsyncMock(return_value=True)

    with pytest.raises(ScreenshotLoadError) as exc_info:
        await shot._navigate_dynamic_page(page, 1234567890)
    assert not isinstance(exc_info.value, Notfound)


@pytest.mark.asyncio
async def test_navigate_dynamic_page_opus_404_fallback_transient_not_notfound() -> None:
    """opus 404 但 fallback 仅瞬时失败时，不能因首个 URL 404 就误报「动态不存在」。"""
    from utils.screenshot.screenshot import (
        DynamicScreenshot,
        Notfound,
        ScreenshotLoadError,
    )

    page = AsyncMock()
    page.url = "https://t.bilibili.com/1234567890"
    page.goto = AsyncMock(
        side_effect=[
            MagicMock(status=404),
            MagicMock(status=200),
        ]
    )
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    shot = DynamicScreenshot()
    shot._wait_for_dynamic_content = AsyncMock(return_value=False)
    shot._is_opus_page_ready = AsyncMock(return_value=True)
    shot._find_dynamic_card = AsyncMock(return_value=None)
    shot._is_login_interstitial = AsyncMock(return_value=False)

    with pytest.raises(ScreenshotLoadError) as exc_info:
        await shot._navigate_dynamic_page(page, 1234567890)
    assert not isinstance(exc_info.value, Notfound)
