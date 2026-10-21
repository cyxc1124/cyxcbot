"""Default TLS must not regain distrusted roots from a host or frozen package."""

import hashlib
import runpy
import ssl
import sys
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import certifi
import click
import nonebot
import pytest
from aiohttp import connector, web

from shared.config.proxy import ProxyConfig
from shared.db import alembic_repair
from shared.security.tls import configure_aiohttp_tls
from tests.test_x_https_proxy import tls_contexts as tls_contexts
from utils.x_api import create_session

_AFFECTED_ROOT = Path(__file__).parent / "fixtures" / "emsign_ecc_root_ca_g3.pem"
_AFFECTED_FINGERPRINT = (
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
)


def _fingerprints(context):
    return {
        hashlib.sha256(cert).hexdigest()
        for cert in context.get_ca_certs(binary_form=True)
    }


@pytest.fixture(autouse=True)
def restore_default_context(monkeypatch):
    monkeypatch.setattr(
        connector, "_SSL_CONTEXT_VERIFIED", connector._SSL_CONTEXT_VERIFIED
    )


@pytest.mark.parametrize("scheme", [None, "http", "https", "socks5"])
async def test_default_connectors_drop_previously_trusted_root(monkeypatch, scheme):
    stale_context = ssl.create_default_context(cafile=str(_AFFECTED_ROOT))
    assert _AFFECTED_FINGERPRINT in _fingerprints(stale_context)
    monkeypatch.setattr(connector, "_SSL_CONTEXT_VERIFIED", stale_context)
    proxy = (
        ProxyConfig(enabled=True, scheme=scheme, host="127.0.0.1", port=1080)
        if scheme
        else None
    )
    async with create_session(proxy) as session:
        request = SimpleNamespace(ssl=True, is_ssl=lambda: True)
        assert session.connector._get_ssl_context(request) is stale_context

        # Simulate stale environment paths and Windows' implicit ROOT/CA loading.
        monkeypatch.setenv("SSL_CERT_FILE", str(_AFFECTED_ROOT))
        monkeypatch.setenv("SSL_CERT_DIR", str(_AFFECTED_ROOT.parent))

        def reject_platform_loading(*args, **kwargs):
            pytest.fail("The default context loaded platform trust")

        monkeypatch.setattr(
            ssl.SSLContext, "load_default_certs", reject_platform_loading
        )
        monkeypatch.setattr(
            ssl.SSLContext, "set_default_verify_paths", reject_platform_loading
        )
        configure_aiohttp_tls()
        context = session.connector._get_ssl_context(request)
        expected = ssl.create_default_context(cafile=certifi.where())
        assert _fingerprints(context) == _fingerprints(expected)
        assert _AFFECTED_FINGERPRINT not in _fingerprints(context)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname


def test_missing_bundle_fails_without_system_fallback(monkeypatch, tmp_path):
    previous = connector._SSL_CONTEXT_VERIFIED
    monkeypatch.setattr(certifi, "where", lambda: str(tmp_path / "missing.pem"))
    with pytest.raises(FileNotFoundError):
        configure_aiohttp_tls()
    assert connector._SSL_CONTEXT_VERIFIED is previous


def test_changed_aiohttp_cache_fails_closed(monkeypatch):
    monkeypatch.delattr(connector, "_SSL_CONTEXT_VERIFIED")
    with pytest.raises(RuntimeError, match="Unsupported aiohttp"):
        configure_aiohttp_tls()


@pytest.mark.parametrize("protocol", ["https", "wss"])
@pytest.mark.parametrize(
    "trust",
    ["default_trusted", "default_untrusted", "explicit_trusted", "wrong_hostname"],
)
async def test_tls_connections_keep_verification(
    monkeypatch, tmp_path, tls_contexts, protocol, trust
):
    server_context, private_context = tls_contexts
    server_context.set_alpn_protocols(("http/1.1",))
    alpn = []

    async def respond(request):
        alpn.append(
            request.transport.get_extra_info("ssl_object").selected_alpn_protocol()
        )
        if protocol == "wss":
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_str("ok")
            await ws.close()
            return ws
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=server_context)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    url = f"{protocol}://127.0.0.1:{port}/"
    try:
        if trust in ("default_trusted", "wrong_hostname"):
            bundle = tmp_path / "cert.pem"
            monkeypatch.setattr(certifi, "where", lambda: str(bundle))
        if trust == "default_untrusted":
            monkeypatch.setattr(connector, "_SSL_CONTEXT_VERIFIED", private_context)
        configure_aiohttp_tls()

        kwargs = {}
        if trust == "explicit_trusted":
            kwargs["ssl"] = private_context
        if trust == "wrong_hostname":
            kwargs["server_hostname"] = "wrong.invalid"

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=3)
        ) as session:

            async def fetch():
                if protocol == "wss":
                    async with session.ws_connect(url, **kwargs) as ws:
                        return (await ws.receive()).data
                async with session.get(url, **kwargs) as response:
                    return await response.text()

            if trust in ("default_untrusted", "wrong_hostname"):
                with pytest.raises(aiohttp.ClientConnectorCertificateError):
                    await fetch()
                assert not alpn
            else:
                assert await fetch() == "ok"
                if trust == "default_trusted":
                    assert alpn == ["http/1.1"]
    finally:
        await runner.cleanup()


def test_startup_installs_policy_before_nonebot_init(monkeypatch, tmp_path):
    stale_context = ssl.create_default_context(cafile=str(_AFFECTED_ROOT))
    monkeypatch.setattr(connector, "_SSL_CONTEXT_VERIFIED", stale_context)
    monkeypatch.setattr(
        alembic_repair, "repair_alembic_version_if_needed", lambda url: None
    )
    monkeypatch.setattr(click, "confirm", click.confirm)
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DRIVER", "~fastapi+~httpx+~websockets")
    monkeypatch.chdir(tmp_path)

    class ReachedInit(Exception):
        pass

    def stop_at_init(*args, **kwargs):
        context = connector._SSL_CONTEXT_VERIFIED
        expected = ssl.create_default_context(cafile=certifi.where())
        assert _fingerprints(context) == _fingerprints(expected)
        assert _AFFECTED_FINGERPRINT not in _fingerprints(context)
        raise ReachedInit

    monkeypatch.setattr(nonebot, "init", stop_at_init)
    with pytest.raises(ReachedInit):
        runpy.run_path(str(Path(__file__).resolve().parents[1] / "bot.py"))


def test_probe_startup_installs_policy_before_download(monkeypatch, tmp_path):
    from scripts import douyin_link_probe as probe

    stale_context = ssl.create_default_context(cafile=str(_AFFECTED_ROOT))
    monkeypatch.setattr(connector, "_SSL_CONTEXT_VERIFIED", stale_context)
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(sys, "argv", ["douyin_link_probe.py", "direct", "--no-db"])
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.chdir(tmp_path)

    async def check_before_download(args):
        async with aiohttp.ClientSession() as session:
            request = SimpleNamespace(ssl=True, is_ssl=lambda: True)
            context = session.connector._get_ssl_context(request)
            assert _AFFECTED_FINGERPRINT not in _fingerprints(context)
            assert _fingerprints(context) == _fingerprints(
                ssl.create_default_context(cafile=certifi.where())
            )
        return 0

    monkeypatch.setattr(probe, "_async_main", check_before_download)
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 0
