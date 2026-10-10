"""HTTPS proxy transport must protect CONNECT and proxy credentials with TLS."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import ssl
from datetime import datetime, timedelta, timezone

import aiohttp
import pytest
from aiohttp_socks import ProxyError
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from shared.config.proxy import ProxyConfig
from utils.x_api import create_session


@pytest.fixture
def tls_contexts(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local proxy test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    x509.DNSName("api.x.invalid"),
                    x509.DNSName("t.co"),
                    x509.DNSName("video.twimg.invalid"),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    return server_context, ssl.create_default_context(cafile=str(cert_path))


async def test_https_proxy_starts_with_tls_and_does_not_fall_back_to_direct():
    loop = asyncio.get_running_loop()
    first_packet = loop.create_future()
    target_connections = []

    async def capture(reader, writer):
        packet = await reader.read(4096)
        if not first_packet.done():
            first_packet.set_result(packet)
        writer.close()
        await writer.wait_closed()

    def target_connected(reader, writer):
        target_connections.append(writer)
        writer.close()

    proxy_server = await asyncio.start_server(capture, "127.0.0.1", 0)
    target_server = await asyncio.start_server(target_connected, "127.0.0.1", 0)
    async with proxy_server, target_server:
        proxy_port = proxy_server.sockets[0].getsockname()[1]
        target_port = target_server.sockets[0].getsockname()[1]
        async with create_session(
            ProxyConfig(
                enabled=True,
                scheme="https",
                host="127.0.0.1",
                port=proxy_port,
                username="user@proxy",
                password="p@ss:/#%",
            )
        ) as session:
            with pytest.raises((aiohttp.ClientError, asyncio.TimeoutError, ProxyError)):
                await session.get(f"https://127.0.0.1:{target_port}/", timeout=1)

        packet = await asyncio.wait_for(first_packet, 1)
        assert packet.startswith(b"\x16\x03"), packet[:32]
        assert b"CONNECT" not in packet
        assert b"Proxy-Authorization" not in packet
        assert b"user@proxy" not in packet
        assert not target_connections


async def test_https_proxy_connect_auth_and_redirects_stay_inside_tls(tls_contexts):
    server_context, client_context = tls_contexts
    connects = []
    requests = []
    errors = []
    finished = []

    async def proxy_handler(reader, writer):
        done = asyncio.get_running_loop().create_future()
        finished.append(done)
        try:
            connects.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await writer.start_tls(server_context)
            request = await reader.readuntil(b"\r\n\r\n")
            requests.append(request)
            path = request.split(b" ", 2)[1]
            if path == b"/first":
                response = b"HTTP/1.1 302 Found\r\nLocation: https://t.co/second\r\n"
                body = b""
            elif path == b"/second":
                response = b"HTTP/1.1 302 Found\r\nLocation: https://video.twimg.invalid/final\r\n"
                body = b""
            else:
                response = b"HTTP/1.1 200 OK\r\n"
                body = b"proxied media"
            writer.write(
                response
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        except Exception as exc:
            errors.append(exc)
        finally:
            writer.close()
            await writer.wait_closed()
            done.set_result(None)

    server = await asyncio.start_server(
        proxy_handler, "127.0.0.1", 0, ssl=server_context
    )
    async with server:
        port = server.sockets[0].getsockname()[1]
        async with create_session(
            ProxyConfig(
                enabled=True,
                scheme="https",
                host="127.0.0.1",
                port=port,
                username="user@proxy",
                password="p@ss:/#%",
            )
        ) as session:
            # 仅信任本测试生成的证书，仍校验代理和隧道目标的主机名。
            session.connector._ssl = client_context
            async with session.get(
                "https://api.x.invalid/first", timeout=3
            ) as response:
                assert await response.read() == b"proxied media"
                assert len(response.history) == 2
        await asyncio.wait_for(asyncio.gather(*finished), 1)

    auth = base64.b64encode(b"user@proxy:p@ss:/#%")
    assert not errors
    assert len(connects) == len(requests) == 3
    assert [header.split(b"\r\n", 1)[0] for header in connects] == [
        b"CONNECT api.x.invalid:443 HTTP/1.1",
        b"CONNECT t.co:443 HTTP/1.1",
        b"CONNECT video.twimg.invalid:443 HTTP/1.1",
    ]
    assert all(b"Proxy-Authorization: Basic " + auth in header for header in connects)
    assert all(b"Proxy-Authorization" not in request for request in requests)


async def test_https_proxy_rejects_untrusted_certificate(tls_contexts):
    server_context, _ = tls_contexts
    requests = []

    def proxy_connected(reader, writer):
        requests.append(writer)
        writer.close()

    server = await asyncio.start_server(
        proxy_connected, "127.0.0.1", 0, ssl=server_context
    )
    async with server:
        port = server.sockets[0].getsockname()[1]
        async with create_session(
            ProxyConfig(enabled=True, scheme="https", host="127.0.0.1", port=port)
        ) as session:
            with pytest.raises(aiohttp.ClientConnectorCertificateError):
                await session.get("https://api.x.invalid/", timeout=1)
    assert not requests
