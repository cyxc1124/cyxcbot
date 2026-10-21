"""Use reviewed Mozilla roots for default outbound Python TLS contexts."""

import ssl

import certifi
import httpx
import httpx._config
import httpx._transports.default
from aiohttp import connector

from shared.security.ca import check_trust_store

_create_context = ssl.create_default_context
_httpx_context = httpx._config.create_ssl_context


def create_client_ssl_context() -> ssl.SSLContext:
    context = _create_context(cafile=certifi.where())
    check_trust_store(context)
    return context


def create_http_ssl_context() -> ssl.SSLContext:
    context = create_client_ssl_context()
    context.set_alpn_protocols(("http/1.1",))
    if context.post_handshake_auth is not None:
        context.post_handshake_auth = True
    return context


def _default_context(
    purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None
):
    if purpose == ssl.Purpose.SERVER_AUTH and all(
        item is None for item in (cafile, capath, cadata)
    ):
        return create_client_ssl_context()
    return _create_context(purpose, cafile=cafile, capath=capath, cadata=cadata)


def _httpx_default_context(verify=True, cert=None, trust_env=True):
    # Only CA environment overrides are excluded; HTTPX still resolves env proxies.
    context = _httpx_context(verify=verify, cert=cert, trust_env=False)
    if verify is True:
        check_trust_store(context)
    return context


def configure_aiohttp_tls() -> None:
    if not hasattr(connector, "_SSL_CONTEXT_VERIFIED"):
        raise RuntimeError("Unsupported aiohttp default TLS context cache")

    context = create_client_ssl_context()
    context.set_alpn_protocols(("http/1.1",))
    # aiohttp 3.14 caches this at import; drivers and proxy connectors share it.
    connector._SSL_CONTEXT_VERIFIED = context


def configure_tls() -> None:
    configure_aiohttp_tls()
    # urllib retains a separate alias; asyncio/WSS and HTTPcore proxies use ssl.
    ssl.create_default_context = _default_context
    ssl._create_default_https_context = _default_context
    # HTTPX imports this factory into its transport and public module at import.
    httpx.create_ssl_context = _httpx_default_context
    httpx._config.create_ssl_context = _httpx_default_context
    httpx._transports.default.create_ssl_context = _httpx_default_context
