"""并发调用全局截图便捷函数时，同时打开的截图数不得超过信号量上限。"""

from __future__ import annotations

import asyncio

import utils.screenshot.screenshot as ss


def test_get_dynamic_screenshot_caps_concurrency(monkeypatch) -> None:
    active = 0
    peak = 0

    async def fake_capture(dynamic_id: int):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return b"img", None, None
        finally:
            active -= 1

    # 跳过浏览器懒初始化，直接替换实际截图实现
    monkeypatch.setattr(ss.dynamic_screenshot, "browser_context", object())
    monkeypatch.setattr(ss.dynamic_screenshot, "get_dynamic_screenshot", fake_capture)

    async def run() -> None:
        await asyncio.gather(*(ss.get_dynamic_screenshot(i) for i in range(12)))

    asyncio.run(run())

    assert peak <= ss._SCREENSHOT_CONCURRENCY
