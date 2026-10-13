"""Media downloads use decoded sizes while preserving HTTP completeness checks."""

import asyncio
import gzip
import random
import zlib
from compression import zstd
from pathlib import Path

import aiohttp
import brotli
import pytest

from utils.douyin_api.download import (
    _DOWNLOAD_CHUNK_BYTES,
    _decode_stream,
    _persist_stream,
    download_file,
)


def _response(
    body: bytes,
    *,
    status: int = 200,
    encoding: str | None = None,
    content_length: int | None = None,
    content_range: str | None = None,
) -> bytes:
    headers = [
        f"HTTP/1.1 {status} Test",
        "Connection: close",
        f"Content-Length: {len(body) if content_length is None else content_length}",
    ]
    if encoding is not None:
        headers.append(f"Content-Encoding: {encoding}")
    if content_range is not None:
        headers.append(f"Content-Range: {content_range}")
    return "\r\n".join(headers).encode() + b"\r\n\r\n" + body


@pytest.fixture
async def media_server():
    responses: list[bytes] = []

    async def handle(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(responses.pop(0))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/video", responses
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("status", [200, 206])
@pytest.mark.parametrize("encoding", [None, "gzip"])
@pytest.mark.parametrize("payload", [b"media content" * 100, b"x"])
async def test_complete_download_keeps_decoded_media(
    media_server, tmp_path: Path, status: int, encoding: str | None, payload: bytes
):
    url, responses = media_server
    body = gzip.compress(payload) if encoding else payload
    responses.append(
        _response(
            body,
            status=status,
            encoding=encoding,
            content_range=f"bytes 0-{len(body) - 1}/{len(body)}"
            if status == 206
            else None,
        )
    )
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert await download_file(url, destination, session, max_bytes=len(payload))
    assert destination.read_bytes() == payload
    assert not destination.with_suffix(".mp4.tmp").exists()


@pytest.mark.parametrize("encoding", [None, "gzip"])
async def test_truncated_http_body_preserves_existing_file(
    media_server, tmp_path: Path, encoding: str | None
):
    url, responses = media_server
    payload = b"media content" * 100
    body = gzip.compress(payload) if encoding else payload
    responses.append(_response(body, encoding=encoding, content_length=len(body) + 1))
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_decoded_size_limit_removes_partial_download(
    media_server, tmp_path: Path
):
    url, responses = media_server
    payload = b"media content" * 100
    body = gzip.compress(payload)
    assert len(body) < len(payload) // 2
    responses.append(_response(body, encoding="gzip"))
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    async with aiohttp.ClientSession() as session:
        assert not await download_file(
            url, destination, session, max_bytes=len(payload) // 2
        )
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()


@pytest.mark.parametrize("encoding", [None, "gzip"])
async def test_partial_range_is_rejected(media_server, tmp_path: Path, encoding):
    url, responses = media_server
    payload = b"media content" * 100
    body = gzip.compress(payload) if encoding else payload
    responses.append(
        _response(
            body,
            status=206,
            encoding=encoding,
            content_range=f"bytes 0-{len(body) - 1}/{len(body) + 1}",
        )
    )
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert not destination.exists()
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_complete_identity_range_length_mismatch_is_rejected(
    media_server, tmp_path: Path
):
    url, responses = media_server
    responses.append(_response(b"media", status=206, content_range="bytes 0-5/6"))
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert not destination.exists()
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_complete_gzip_range_length_mismatch_is_rejected(
    media_server, tmp_path: Path
):
    url, responses = media_server
    body = gzip.compress(b"media content" * 100)
    responses.append(
        _response(
            body,
            status=206,
            encoding="gzip",
            content_range=f"bytes 0-{len(body)}/{len(body) + 1}",
        )
    )
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert not destination.exists()
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_chunked_gzip_range_without_encoded_length_is_rejected(
    media_server, tmp_path: Path
):
    url, responses = media_server
    body = gzip.compress(b"media content" * 100)
    responses.append(
        (
            "HTTP/1.1 206 Test\r\n"
            "Connection: close\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Content-Encoding: gzip\r\n"
            f"Content-Range: bytes 0-{len(body) - 1}/{len(body)}\r\n\r\n"
            f"{len(body):x}\r\n"
        ).encode()
        + body
        + b"\r\n0\r\n\r\n"
    )
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert not destination.exists()
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_forbidden_response_falls_back_to_httpx_with_gzip(
    media_server, tmp_path: Path
):
    url, responses = media_server
    payload = b"media content" * 100
    responses.extend(
        [_response(b"", status=403), _response(gzip.compress(payload), encoding="gzip")]
    )
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert await download_file(url, destination, session, max_bytes=len(payload))
    assert destination.read_bytes() == payload
    assert not responses


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("trailer_error", ["truncated", "bad_crc"])
async def test_invalid_gzip_preserves_existing_file(
    media_server, tmp_path: Path, fallback: bool, trailer_error: str
):
    url, responses = media_server
    body = gzip.compress(random.Random(0).randbytes(4096))
    body = body[:-256] if trailer_error == "truncated" else body[:-8] + b"bad-crc!"
    if fallback:
        responses.append(_response(b"", status=403))
    responses.append(_response(body, encoding="gzip"))
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()


_CODINGS = [
    pytest.param("gzip", gzip.compress, id="gzip"),
    pytest.param("deflate", zlib.compress, id="deflate"),
    pytest.param(
        "deflate",
        lambda data: zlib.compress(data, wbits=-zlib.MAX_WBITS),
        id="raw-deflate",
    ),
    pytest.param("br", brotli.compress, id="br"),
    pytest.param("zstd", zstd.compress, id="zstd"),
    pytest.param(
        "gzip, deflate",
        lambda data: zlib.compress(gzip.compress(data)),
        id="stacked",
    ),
]


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("encoding, compress", _CODINGS)
async def test_supported_codings_decode_large_complete_bodies(
    media_server, tmp_path: Path, fallback, encoding, compress
):
    url, responses = media_server
    payload = b"media content" * 50000
    if fallback:
        responses.append(_response(b"", status=403))
    responses.append(_response(compress(payload), encoding=encoding))
    destination = tmp_path / "video.mp4"
    async with aiohttp.ClientSession() as session:
        assert await download_file(url, destination, session, max_bytes=len(payload))
    assert destination.read_bytes() == payload
    assert not destination.with_suffix(".mp4.tmp").exists()


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("encoding, compress", _CODINGS)
async def test_truncated_codings_preserve_existing_file(
    media_server, tmp_path: Path, fallback, encoding, compress
):
    url, responses = media_server
    body = compress(random.Random(0).randbytes(4096))[:-1]
    if fallback:
        responses.append(_response(b"", status=403))
    responses.append(_response(body, encoding=encoding))
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()


@pytest.mark.parametrize("encoding, compress", _CODINGS)
async def test_decoding_keeps_output_chunks_bounded(encoding, compress):
    payload = b"media content" * 50000

    async def chunks():
        yield compress(payload)

    decoded_size = 0
    async for chunk in _decode_stream(chunks(), encoding):
        assert len(chunk) <= _DOWNLOAD_CHUNK_BYTES
        decoded_size += len(chunk)
    assert decoded_size == len(payload)


@pytest.mark.parametrize(
    "encoding, compress", [("gzip", gzip.compress), ("zstd", zstd.compress)]
)
@pytest.mark.parametrize("separate_chunks", [False, True])
async def test_multiple_complete_members_are_decoded(
    encoding, compress, separate_chunks
):
    first, second = b"first member", b"second member"
    bodies = [compress(first), compress(second)]

    async def chunks():
        for body in bodies if separate_chunks else [b"".join(bodies)]:
            yield body

    result = b"".join([chunk async for chunk in _decode_stream(chunks(), encoding)])
    assert result == first + second


@pytest.mark.parametrize(
    "encoding, compress", [("gzip", gzip.compress), ("zstd", zstd.compress)]
)
async def test_incomplete_second_member_is_rejected(
    media_server, tmp_path: Path, encoding, compress
):
    url, responses = media_server
    body = compress(b"first member") + compress(b"second member")[:-1]
    responses.append(_response(body, encoding=encoding))
    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    async with aiohttp.ClientSession() as session:
        assert not await download_file(url, destination, session)
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()


async def test_cancelled_gzip_stream_preserves_existing_file(tmp_path: Path):
    body = gzip.compress(random.Random(0).randbytes(4096))
    started = asyncio.Event()

    async def chunks():
        yield body[: len(body) // 2]
        started.set()
        await asyncio.Event().wait()

    destination = tmp_path / "video.mp4"
    destination.write_bytes(b"previous")
    task = asyncio.create_task(
        _persist_stream(
            _decode_stream(chunks(), "gzip"), destination, None, max_bytes=8192
        )
    )
    await started.wait()
    assert destination.with_suffix(".mp4.tmp").exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert destination.read_bytes() == b"previous"
    assert not destination.with_suffix(".mp4.tmp").exists()
