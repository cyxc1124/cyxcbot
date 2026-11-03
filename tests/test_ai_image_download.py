"""Only QQ CDN images are downloaded, with bounded sizes and no redirects."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import ai_image_helpers  # noqa: F401
import pytest
from PIL import Image

from plugins.ai_image_detector import image


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://127.0.0.1/a.png",
        "https://gchat.qpic.cn.evil.test/a.png",
        "https://evilqpic.cn/a.png",
        "https://user:pass@gchat.qpic.cn/a.png",
        "https://gchat.qpic.cn:8080/a.png",
        "https://gchat.qpic.cn:bad/a.png",
        "https://evil.test/#https://gchat.qpic.cn/",
        "https://multimedia.nt.qq.com.cn.evil.test/a",
        "https://evilmultimedia.nt.qq.com.cn/a",
    ],
)
def test_reject_non_cdn_addresses(url):
    with pytest.raises(image.ImageDetectionError):
        image.qq_image_url(url)


@pytest.mark.parametrize(
    "host", ["gchat.qpic.cn", "multimedia.nt.qq.com", "multimedia.nt.qq.com.cn"]
)
def test_upgrade_qq_cdn_https_without_losing_download_signature(host):
    assert (
        image.qq_image_url(
            f"http://{host}/download?appid=1407&fileid=test&rkey=test#fragment"
        )
        == f"https://{host}/download?appid=1407&fileid=test&rkey=test"
    )


@pytest.fixture
def response(monkeypatch):
    response = MagicMock()
    response.status = 200
    response.content_length = None
    response.__aenter__.return_value = response
    session = MagicMock()
    session.get.return_value = response
    session.__aenter__.return_value = session
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(image.aiohttp, "ClientSession", factory)
    return SimpleNamespace(value=response, session=session, factory=factory)


@pytest.mark.parametrize(
    "host", ["gchat.qpic.cn", "multimedia.nt.qq.com", "multimedia.nt.qq.com.cn"]
)
async def test_download_keeps_original_bytes_and_refuses_redirects(response, host):
    async def chunks(size):
        yield b"original"
        yield b" metadata"

    response.value.content.iter_chunked.side_effect = chunks
    assert await image.download_image(f"https://{host}/a") == b"original metadata"
    assert response.session.get.call_args.kwargs["allow_redirects"] is False
    response.value.status = 302
    with pytest.raises(image.ImageDetectionError, match="下载失败"):
        await image.download_image(f"https://{host}/a")


async def test_stream_limit_works_without_content_length(response, monkeypatch):
    monkeypatch.setattr(image, "MAX_IMAGE_BYTES", 4)

    async def chunks(size):
        yield b"123"
        yield b"45"

    response.value.content.iter_chunked.side_effect = chunks
    with pytest.raises(image.ImageDetectionError, match="超过"):
        await image.download_image("https://gchat.qpic.cn/a")


async def test_content_length_limit_prevents_streaming(response):
    response.value.content_length = image.MAX_IMAGE_BYTES + 1
    with pytest.raises(image.ImageDetectionError, match="超过"):
        await image.download_image("https://gchat.qpic.cn/a")
    response.value.content.iter_chunked.assert_not_called()


def test_media_type_comes_from_file_bytes():
    stream = BytesIO()
    Image.new("RGB", (8, 8)).save(stream, format="PNG")
    assert image.image_media_type(stream.getvalue()) == "image/png"
    with pytest.raises(image.ImageDetectionError, match="损坏"):
        image.image_media_type(b"not an image")
