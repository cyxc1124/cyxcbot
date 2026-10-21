"""Real bundled Chromium must enforce its private trust policy before cookies."""

import asyncio
from contextlib import closing

import pytest
from playwright.async_api import Error, async_playwright

from shared.security import browser
from shared.security.playwright import configure_playwright_tls


async def test_browser_policy_render_and_private_profile_cleanup(monkeypatch, tmp_path):
    directory = tmp_path / "浏览器 profile"
    directory.mkdir()
    monkeypatch.setattr(browser.tempfile, "tempdir", str(directory))
    profiles = []
    seed = browser._seed_profile

    def record(profile):
        profiles.append(profile)
        return seed(profile)

    monkeypatch.setattr(browser, "_seed_profile", record)
    configure_playwright_tls()
    async with async_playwright() as pw:
        context, resources = await browser.create_browser_context(
            pw,
            headless=True,
            args=["--no-sandbox", "--disable-web-security", "--no-zygote"],
        )
        try:
            assert await context.cookies() == []
            await context.add_cookies(
                [
                    {
                        "name": "audit",
                        "value": "cookie",
                        "url": "https://www.bilibili.com/",
                    }
                ]
            )
            assert (await context.cookies("https://www.bilibili.com/"))[0][
                "value"
            ] == "cookie"
            page = await context.new_page()
            await page.set_content(
                '<main style="font-size:24px">TLS verified screenshot</main>'
            )
            assert await page.locator("main").inner_text() == "TLS verified screenshot"
            assert (await page.screenshot()).startswith(b"\x89PNG\r\n\x1a\n")
        finally:
            await resources.aclose()
        assert profiles and all(not profile.exists() for profile in profiles)


@pytest.mark.parametrize("policy", ["missing", "distrust_ignored"])
async def test_browser_fails_closed_if_certificate_database_is_not_honored(
    monkeypatch, policy
):
    profiles = []
    seed = browser._seed_profile

    def corrupt(profile):
        contexts = seed(profile)
        profiles.append(profile)
        database = profile / "Default" / "ServerCertificate"
        if policy == "missing":
            database.unlink()
        else:
            import sqlite3

            with closing(sqlite3.connect(database)) as db:
                db.execute(
                    "DELETE FROM certificates WHERE trust_settings = ?",
                    (b"\x0a\x02\x08\x02",),
                )
                db.commit()
        return contexts

    monkeypatch.setattr(browser, "_seed_profile", corrupt)
    configure_playwright_tls()
    async with async_playwright() as pw:
        with pytest.raises((RuntimeError, Error)):
            await browser.create_browser_context(
                pw, headless=True, args=["--no-sandbox"]
            )
        assert all(not profile.exists() for profile in profiles)


async def test_browser_probe_cleans_up_idle_tls_preconnections(monkeypatch):
    start_server = asyncio.start_server
    connections = []

    async def preconnect(*args, **kwargs):
        server = await start_server(*args, **kwargs)
        connections.append(
            await asyncio.open_connection(
                "127.0.0.1", server.sockets[0].getsockname()[1]
            )
        )
        return server

    monkeypatch.setattr(browser.asyncio, "start_server", preconnect)
    configure_playwright_tls()
    resources = None
    try:
        async with async_playwright() as pw:
            async with asyncio.timeout(15):
                _, resources = await browser.create_browser_context(
                    pw, headless=True, args=["--no-sandbox"]
                )
            await resources.aclose()
            resources = None
            for reader, _ in connections:
                assert await asyncio.wait_for(reader.read(1), 1) == b""
    finally:
        for _, writer in connections:
            writer.close()
            await writer.wait_closed()
        if resources is not None:
            await resources.aclose()
