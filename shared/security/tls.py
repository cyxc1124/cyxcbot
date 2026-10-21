"""Use the bundled Mozilla trust store for aiohttp's default TLS verification."""

import ssl

import certifi
from aiohttp import connector


def configure_aiohttp_tls() -> None:
    if not hasattr(connector, "_SSL_CONTEXT_VERIFIED"):
        raise RuntimeError("Unsupported aiohttp default TLS context cache")

    context = ssl.create_default_context(cafile=certifi.where())
    context.set_alpn_protocols(("http/1.1",))
    # aiohttp 3.14 caches this at import; drivers and proxy connectors share it.
    connector._SSL_CONTEXT_VERIFIED = context
