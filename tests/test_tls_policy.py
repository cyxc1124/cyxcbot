"""Default Python/Node TLS must reject stale host and environment trust."""

import asyncio
import base64
import hashlib
import json
import os
import ssl
import subprocess
import sys
import urllib.request
from contextlib import suppress
from email.message import Message
from pathlib import Path
from unittest.mock import Mock

import certifi
import httpcore._ssl
import httpx
import pytest
import websockets
from aiohttp import web
from nonebot.drivers import Request
from nonebot.drivers.httpx import Session
from nonebot.drivers.websockets import Mixin
from playwright._impl._driver import compute_driver_executable

from shared.security.ca import DISTRUSTED_ROOTS, fingerprints
from shared.security.playwright import node_environment
from shared.security.tls import (
    configure_tls,
    create_client_ssl_context,
    create_http_ssl_context,
)
from tests.test_x_https_proxy import tls_contexts as tls_contexts

_AFFECTED = Path(__file__).parent / "fixtures" / "emsign_ecc_root_ca_g3.pem"


@pytest.fixture
def policy(monkeypatch, tls_policy_state):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("SSL_CERT_FILE", str(_AFFECTED))
    monkeypatch.setenv("SSL_CERT_DIR", str(_AFFECTED.parent))
    configure_tls()


def test_default_factories_exclude_system_and_environment_roots(policy, monkeypatch):
    def reject(*args, **kwargs):
        pytest.fail("Default client loaded platform roots")

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", reject)
    monkeypatch.setattr(ssl.SSLContext, "set_default_verify_paths", reject)
    expected = fingerprints(create_client_ssl_context())
    for context in (
        ssl.create_default_context(),
        ssl._create_default_https_context(),
        httpx.create_ssl_context(),
        httpcore._ssl.default_ssl_context(),
    ):
        assert fingerprints(context) == expected
        assert not fingerprints(context) & DISTRUSTED_ROOTS
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname


def test_explicit_trust_and_client_auth_are_preserved(policy, tls_contexts, tmp_path):
    _, context = tls_contexts
    assert httpx.create_ssl_context(verify=context) is context
    assert fingerprints(
        ssl.create_default_context(cafile=str(tmp_path / "cert.pem"))
    ) == fingerprints(context)
    server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    assert not server_context.check_hostname
    assert server_context.verify_mode == ssl.CERT_NONE


@pytest.mark.parametrize(
    "client",
    ["urllib", "urllib_explicit", "httpx", "nonebot_httpx", "websockets", "nonebot_ws"],
)
@pytest.mark.parametrize("trust", ["trusted", "untrusted", "wrong_hostname"])
async def test_actual_default_client_connections(
    policy, monkeypatch, tmp_path, tls_contexts, client, trust
):
    server_context, _ = tls_contexts
    server_context.set_alpn_protocols(("http/1.1",))
    received = []

    async def respond(request):
        if client.startswith("urllib"):
            assert (
                request.transport.get_extra_info("ssl_object").selected_alpn_protocol()
                == "http/1.1"
            )
        received.append(request.headers.get("Cookie"))
        if client in ("websockets", "nonebot_ws"):
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
    host = "localhost" if trust == "wrong_hostname" else "127.0.0.1"
    scheme = "wss" if client in ("websockets", "nonebot_ws") else "https"
    url = f"{scheme}://{host}:{port}/"
    if trust != "untrusted":
        monkeypatch.setattr(certifi, "where", lambda: str(tmp_path / "cert.pem"))
    headers = {"Cookie": "audit=value"}

    async def fetch():
        if client.startswith("urllib"):

            def read():
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=headers),
                    timeout=3,
                    **(
                        {"context": create_http_ssl_context()}
                        if client == "urllib_explicit"
                        else {}
                    ),
                ) as response:
                    return response.read().decode()

            return await asyncio.to_thread(read)
        if client == "httpx":
            async with httpx.AsyncClient(timeout=3) as session:
                return (await session.get(url, headers=headers)).text
        if client == "nonebot_httpx":
            async with Session() as session:
                return (
                    await session.request(
                        Request("GET", url, headers=headers, timeout=3)
                    )
                ).content.decode()
        if client == "websockets":
            async with websockets.connect(
                url, proxy=None, additional_headers=headers, open_timeout=3
            ) as ws:
                return await ws.recv()
        async with Mixin().websocket(
            Request("GET", url, headers=headers, timeout=3)
        ) as ws:
            return await ws.receive_text()

    try:
        if trust == "trusted":
            assert await fetch() == "ok"
            assert received == ["audit=value"]
        else:
            with pytest.raises(Exception) as error:
                await fetch()
            assert "certificate" in str(error.value).lower()
            assert not received
    finally:
        await runner.cleanup()


def test_urllib_callers_supply_reviewed_context(monkeypatch):
    from utils.douyin_api import ms_token

    contexts = []

    def open_request(request, *, timeout, context):
        contexts.append(context)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"{}"
        response.headers = Message()
        response.headers["Set-Cookie"] = "msToken=" + "a" * 164
        return response

    monkeypatch.setattr(ms_token.urllib.request, "urlopen", open_request)
    manager = ms_token.MsTokenManager(user_agent="TLS regression")
    assert manager.gen_real_ms_token() == "a" * 164
    assert len(contexts) == 1
    assert all(not fingerprints(context) & DISTRUSTED_ROOTS for context in contexts)


def test_about_update_check_supplies_reviewed_context():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
os.environ['SQLALCHEMY_DATABASE_URL']='sqlite+aiosqlite:///:memory:'
import nonebot
nonebot.init(_env_file=None, sqlalchemy_database_url=os.environ['SQLALCHEMY_DATABASE_URL'], alembic_startup_check=False)
nonebot.require('nonebot_plugin_orm')
from admin.api.v1 import about
from shared.security.ca import DISTRUSTED_ROOTS, fingerprints
from unittest.mock import MagicMock, patch
response=MagicMock()
response.__enter__.return_value=response
response.read.return_value=b'{}'
with patch.object(about, 'urlopen', return_value=response) as opener:
    assert about._fetch_json('https://api.github.com/example') == {}
    context=opener.call_args.kwargs['context']
    assert context.check_hostname
    assert not fingerprints(context) & DISTRUSTED_ROOTS
""",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_node_preload_replaces_all_default_roots_and_handles_spaces(tmp_path):
    from shared.security import playwright as policy

    directory = tmp_path / "policy 中文 with spaces"
    directory.mkdir()
    for name in (
        "node_ca.cjs",
        "node_ca_policy.cjs",
        "distrusted_roots.json",
        "distrusted_keys.json",
    ):
        (directory / name).write_bytes(
            Path(policy.__file__).with_name(name).read_bytes()
        )
    node, _ = compute_driver_executable()
    env = node_environment(
        {
            **os.environ,
            "NODE_EXTRA_CA_CERTS": str(_AFFECTED),
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
            "NODE_OPTIONS": "--max-old-space-size=256",
        },
        policy_dir=directory,
    )
    result = subprocess.run(
        [
            node,
            "-e",
            "const {X509Certificate}=require('node:crypto');console.log(JSON.stringify(require('node:tls').getCACertificates('default').map(c=>new X509Certificate(c).fingerprint256.replaceAll(':','').toLowerCase())))",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert env["NODE_TLS_REJECT_UNAUTHORIZED"] == "1"
    assert set(json.loads(result.stdout)) == fingerprints(create_client_ssl_context())
    assert (
        node_environment(env, policy_dir=directory)["NODE_OPTIONS"]
        == env["NODE_OPTIONS"]
    )


def test_node_missing_or_distrusted_bundle_fails_closed(tmp_path):
    node, _ = compute_driver_executable()
    with pytest.raises(FileNotFoundError):
        node_environment(bundle=tmp_path / "missing.pem")
    result = subprocess.run(
        [node, "-e", "throw new Error('main must not run')"],
        env=node_environment(bundle=_AFFECTED),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "Distrusted incident root" in result.stderr
    assert "Error: main must not run" not in result.stderr


@pytest.mark.parametrize(
    "client", ["httpx", "nonebot_httpx", "websockets", "nonebot_ws"]
)
@pytest.mark.parametrize("trust", ["trusted", "untrusted", "wrong_hostname"])
async def test_https_proxy_default_tls_protects_connect_and_auth(
    policy, monkeypatch, tmp_path, tls_contexts, client, trust
):
    server_context, _ = tls_contexts
    connects = []
    requests = []

    async def proxy(reader, writer):
        try:
            connects.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await writer.start_tls(server_context)
            request = await reader.readuntil(b"\r\n\r\n")
            requests.append(request)
            if client in ("websockets", "nonebot_ws"):
                key = next(
                    line.split(b":", 1)[1].strip()
                    for line in request.split(b"\r\n")
                    if line.lower().startswith(b"sec-websocket-key:")
                )
                accept = base64.b64encode(
                    hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
                )
                writer.write(
                    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
                    + accept
                    + b"\r\n\r\n\x81\x02ok\x88\x02\x03\xe8"
                )
            else:
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
                )
            await writer.drain()
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()

    server = await asyncio.start_server(proxy, "127.0.0.1", 0, ssl=server_context)
    async with server:
        port = server.sockets[0].getsockname()[1]
        proxy_host = "localhost" if trust == "wrong_hostname" else "127.0.0.1"
        monkeypatch.setenv("HTTPS_PROXY", f"https://user:password@{proxy_host}:{port}")
        monkeypatch.setenv("NO_PROXY", "")
        if trust != "untrusted":
            monkeypatch.setattr(certifi, "where", lambda: str(tmp_path / "cert.pem"))

        async def fetch():
            if client == "httpx":
                async with httpx.AsyncClient(timeout=3) as session:
                    return (
                        await session.get(
                            "https://127.0.0.1/", headers={"Cookie": "audit=value"}
                        )
                    ).text
            if client == "nonebot_httpx":
                async with Session() as session:
                    return (
                        await session.request(
                            Request(
                                "GET",
                                "https://127.0.0.1/",
                                headers={"Cookie": "audit=value"},
                                timeout=3,
                            )
                        )
                    ).content.decode()
            if client == "websockets":
                async with websockets.connect(
                    "wss://127.0.0.1/",
                    additional_headers={"Cookie": "audit=value"},
                    open_timeout=3,
                ) as ws:
                    return await ws.recv()
            async with Mixin().websocket(
                Request(
                    "GET",
                    "wss://127.0.0.1/",
                    headers={"Cookie": "audit=value"},
                    timeout=3,
                )
            ) as ws:
                return await ws.receive_text()

        if trust == "trusted":
            assert await fetch() == "ok"
            assert len(connects) == len(requests) == 1
            assert b"Proxy-Authorization: Basic dXNlcjpwYXNzd29yZA==" in connects[0]
            assert b"Cookie: audit=value" in requests[0]
            assert b"Proxy-Authorization:" not in requests[0]
        else:
            with pytest.raises(Exception) as error:
                await fetch()
            assert "certificate" in str(error.value).lower()
            assert not connects and not requests


@pytest.mark.parametrize("trust", ["trusted", "untrusted", "wrong_hostname"])
async def test_node_actual_tls_preserves_certificate_and_hostname_validation(
    tmp_path, tls_contexts, trust
):
    server_context, _ = tls_contexts
    received = []

    async def respond(request):
        received.append(request.headers.get("Cookie"))
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=server_context)
    await site.start()
    node, _ = compute_driver_executable()
    port = site._server.sockets[0].getsockname()[1]
    host = "localhost" if trust == "wrong_hostname" else "127.0.0.1"
    script = "require('node:https').get(process.argv[1],{headers:{Cookie:'audit=value'}},r=>{r.resume();r.on('end',()=>process.exit(r.statusCode===200?0:2))}).on('error',e=>{console.error(e.code);process.exit(1)})"
    try:
        process = await asyncio.create_subprocess_exec(
            node,
            "-e",
            script,
            f"https://{host}:{port}/",
            env=node_environment(
                bundle=None if trust == "untrusted" else tmp_path / "cert.pem"
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, errors = await asyncio.wait_for(process.communicate(), 15)
        assert process.returncode == (0 if trust == "trusted" else 1), errors.decode()
        assert received == (["audit=value"] if trust == "trusted" else [])
    finally:
        await runner.cleanup()
