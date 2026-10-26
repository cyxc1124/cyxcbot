"""Apply Chromium SPKI distrust in a private profile before loading credentials."""

import asyncio
import hashlib
import ipaddress
import sqlite3
import ssl
import tempfile
from contextlib import AsyncExitStack, closing, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _seed_profile(profile: Path) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    certificates = x509.load_pem_x509_certificates(
        Path(__file__).with_name("emudhra_intermediates.pem").read_bytes()
    )
    if len(certificates) != 16:
        raise RuntimeError("Incomplete Chromium incident distrust certificates")

    now = datetime.now(timezone.utc)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CyxcBot TLS probe")])
    root = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    contexts = []
    leaves = []
    for label in ("allowed", "blocked"):
        leaf_key = ec.generate_private_key(ec.SECP256R1())
        leaf = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False
            )
            .sign(key, hashes.SHA256())
        )
        cert_file, key_file = profile / f"{label}.pem", profile / f"{label}.key"
        cert_file.write_bytes(
            leaf.public_bytes(serialization.Encoding.PEM)
            + root.public_bytes(serialization.Encoding.PEM)
        )
        key_file.write_bytes(
            leaf_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        cert_file.unlink()
        key_file.unlink()
        contexts.append(context)
        leaves.append(leaf)

    directory = profile / "Default"
    directory.mkdir()
    # shortcut: Chromium schema v1, update with Playwright if the TLS probes fail.
    with closing(sqlite3.connect(directory / "ServerCertificate")) as db:
        db.execute(
            "CREATE TABLE meta(key LONGVARCHAR PRIMARY KEY NOT NULL, value LONGVARCHAR)"
        )
        db.executemany(
            "INSERT INTO meta VALUES(?, ?)",
            [("version", "1"), ("last_compatible_version", "1")],
        )
        db.execute(
            "CREATE TABLE certificates(sha256hash_hex TEXT PRIMARY KEY, der_cert BLOB NOT NULL, trust_settings BLOB NOT NULL)"
        )
        for cert, trust in [
            *((cert, 2) for cert in certificates),
            (root, 3),
            (leaves[1], 2),
        ]:
            der = cert.public_bytes(serialization.Encoding.DER)
            db.execute(
                "INSERT INTO certificates VALUES(?, ?, ?)",
                (
                    hashlib.sha256(der).hexdigest(),
                    der,
                    b"\x0a\x02\x08" + bytes([trust]),
                ),
            )
        db.commit()
    return tuple(contexts)


async def _verify_profile(context, ssl_contexts) -> None:
    received = []
    connections = set()

    def connected(reader, writer):
        connections.add(writer)
        return respond(reader, writer)

    def abort_connections():
        for writer in tuple(connections):
            writer.transport.abort()

    async def respond(reader, writer):
        try:
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            received.append(writer.get_extra_info("sockname")[1])
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\ncyxcbot-tls"
            )
            await writer.drain()
        except asyncio.IncompleteReadError, ConnectionError, TimeoutError:
            pass
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            connections.discard(writer)

    async with AsyncExitStack() as resources:
        ports = []
        for ssl_context in ssl_contexts:
            server = await asyncio.start_server(
                connected,
                "127.0.0.1",
                0,
                ssl=ssl_context,
                # Pending handshakes have no StreamWriter to abort on uvloop.
                ssl_handshake_timeout=5,
                ssl_shutdown_timeout=1,
            )
            await resources.enter_async_context(server)
            # Chromium can leave idle TLS preconnections behind after closing a page.
            resources.callback(getattr(server, "abort_clients", abort_connections))
            resources.callback(server.close)
            ports.append(server.sockets[0].getsockname()[1])
        page = await context.new_page()
        resources.push_async_callback(page.close)
        response = await page.goto(f"https://127.0.0.1:{ports[0]}/", timeout=10000)
        if (
            response is None
            or response.status != 200
            or await response.text() != "cyxcbot-tls"
        ):
            raise RuntimeError("Chromium did not load its private certificate policy")
        try:
            await page.goto(f"https://127.0.0.1:{ports[1]}/", timeout=10000)
        except Exception as exc:
            if "ERR_CERT_AUTHORITY_INVALID" not in str(exc):
                raise
        else:
            raise RuntimeError("Chromium ignored certificate distrust")
        if ports[0] not in received or ports[1] in received:
            raise RuntimeError("Chromium sent HTTP data to a distrusted certificate")


async def create_browser_context(playwright, **options):
    if proxy := options.get("proxy"):
        # Policy probes must reach this process, never the proxy's loopback.
        options["proxy"] = {
            **proxy,
            "bypass": ",".join(filter(None, (proxy.get("bypass"), "127.0.0.1"))),
        }
    async with AsyncExitStack() as resources:
        profile = resources.enter_context(
            tempfile.TemporaryDirectory(prefix="cyxcbot-chromium-")
        )
        ssl_contexts = _seed_profile(Path(profile))
        context = await playwright.chromium.launch_persistent_context(
            profile, channel="chromium", ignore_https_errors=False, **options
        )
        resources.push_async_callback(context.browser.close)
        resources.push_async_callback(context.close)
        await _verify_profile(context, ssl_contexts)
        return context, resources.pop_all()
