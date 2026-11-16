"""Vision API client: request formats, model listing, balances and failure safety."""

import asyncio
import base64
import json
from io import BytesIO

import ai_image_helpers  # noqa: F401
import httpx
import pytest
from PIL import Image

from shared.config.ai_image import VisionProviderRecord
from shared.config.proxy import ProxyConfig
from utils.vision_api import (
    Balance,
    BalanceItem,
    ModelInfo,
    VisionAPIError,
    VisionImage,
    VisionVerdict,
    balance_provider,
    judge_image,
    list_models,
    parse_verdict,
    prepare_vision_image,
    query_balance,
    sample_image,
)
from utils.vision_api import client as vision_client
from utils.vision_api import image as vision_image

REAL_CLIENT = httpx.AsyncClient
VERDICT = '{"verdict": "ai", "confidence": 87, "reason": "手指  结构\\n异常"}'
PIXELS = VisionImage("image/png", base64.b64encode(b"pixels").decode())


def _provider(api_type="openai", **kwargs):
    return VisionProviderRecord(
        id="p1",
        name="测试模型",
        api_type=api_type,
        model="vision-test",
        api_key=kwargs.pop("api_key", "test-only-key"),
        **kwargs,
    )


def _mock_client(monkeypatch, handler, expected_proxy=None):
    def factory(**kwargs):
        assert kwargs["proxy"] == expected_proxy
        assert kwargs["follow_redirects"] is False
        return REAL_CLIENT(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(vision_client.httpx, "AsyncClient", factory)


def _image(fmt, size, mode="RGB", **options):
    buffer = BytesIO()
    Image.new(mode, size, "red").save(buffer, format=fmt, **options)
    return buffer.getvalue()


async def test_openai_compatible_request_sends_data_url_and_reports_usage(
    monkeypatch,
):
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://gateway.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        body = json.loads(request.content)
        assert body["model"] == "vision-test"
        assert "max_tokens" not in body and "temperature" not in body
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["content"][1]["image_url"]["url"] == (
            "data:image/png;base64," + PIXELS.data
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": f"```json\n{VERDICT}\n```"}}],
                "usage": {"prompt_tokens": 812, "completion_tokens": 41},
            },
        )

    _mock_client(monkeypatch, handle, "http://proxy.test:7890")
    result = await judge_image(
        _provider(base_url="https://gateway.test/v1"),
        PIXELS,
        proxy=ProxyConfig(enabled=True, host="proxy.test", port=7890),
    )
    assert result == VisionVerdict("ai", 87, "手指 结构 异常", 812, 41)
    assert len(calls) == 1


async def test_anthropic_request_sends_both_key_headers_and_reads_text_blocks(
    monkeypatch,
):
    def handle(request):
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "test-only-key"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["max_tokens"] > 0 and body["system"]
        assert body["messages"][0]["content"][0]["source"] == {
            "type": "base64",
            "media_type": "image/png",
            "data": PIXELS.data,
        }
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "thinking", "thinking": '{"verdict": "ai"}'},
                    {
                        "type": "text",
                        "text": '{"verdict": "NOT_AI", "confidence": 101}',
                    },
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 300, "output_tokens": 20},
            },
        )

    _mock_client(monkeypatch, handle)
    result = await judge_image(_provider("anthropic"), PIXELS)
    assert result == VisionVerdict("not_ai", None, "", 300, 20)


async def test_keyless_local_endpoint_sends_no_credentials(monkeypatch):
    def handle(request):
        assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"
        assert "authorization" not in request.headers
        content = [{"type": "text", "text": '{"verdict": "uncertain"}'}]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    _mock_client(monkeypatch, handle)
    provider = _provider(base_url="http://127.0.0.1:11434/v1", api_key="")
    assert (await judge_image(provider, PIXELS)).verdict == "uncertain"


@pytest.mark.parametrize("status", [302, 400, 401, 402, 403, 404, 413, 429, 500])
async def test_http_errors_keep_upstream_text_out_of_the_chat_message(
    monkeypatch, status
):
    def handle(request):
        return httpx.Response(
            status,
            json={"error": {"message": "upstream says test-only-key\nis wrong"}},
        )

    _mock_client(monkeypatch, handle)
    with pytest.raises(VisionAPIError) as error:
        await judge_image(_provider(), PIXELS)
    assert "upstream" not in error.value.message
    assert error.value.detail == "upstream says *** is wrong"


async def test_connection_failure_and_total_timeout_are_safe_errors(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("sensitive-connection-detail")

    _mock_client(monkeypatch, refuse)
    with pytest.raises(VisionAPIError, match="连接失败") as error:
        await judge_image(_provider(), PIXELS)
    assert "sensitive" not in str(error.value)

    async def stall(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    monkeypatch.setattr(vision_client, "TIMEOUT", 0.05)
    _mock_client(monkeypatch, stall)
    with pytest.raises(VisionAPIError, match="超时"):
        await judge_image(_provider(), PIXELS)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": VERDICT, "refusal": "no"}}]},
        {"choices": [{"message": {"content": "看起来像 AI"}}]},
        {"choices": [{"message": {"content": '{"verdict": "maybe"}'}}]},
    ],
)
async def test_unusable_answers_are_errors_not_verdicts(monkeypatch, payload):
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(VisionAPIError):
        await judge_image(_provider(), PIXELS)


def test_parse_verdict_skips_reasoning_and_keeps_raw_text_for_admins():
    text = (
        '<think>{"verdict": "not_ai"}</think>分析：{"note": 1}\n'
        '{"verdict": "ai", "confidence": 60.4, "reason": "' + "长" * 100 + '"}'
    )
    verdict, confidence, reason = parse_verdict(text)
    assert (verdict, confidence, len(reason)) == ("ai", 60, 80)
    with pytest.raises(VisionAPIError) as error:
        parse_verdict("我认为这是  AI 生成的")
    assert error.value.detail == "我认为这是 AI 生成的"


def test_parse_verdict_reads_probabilities_and_braces_in_reasons():
    assert parse_verdict(
        '{"verdict": "ai", "confidence": 0.92, "reason": "背景{重复}纹理"}'
    ) == ("ai", 92, "背景{重复}纹理")
    assert parse_verdict('{"result": {"verdict": "uncertain", "confidence": 1.0}}') == (
        "uncertain",
        100,
        "",
    )
    # 整数仍按百分数理解。
    assert parse_verdict('{"verdict": "not_ai", "confidence": 1}')[1] == 1


async def test_openai_model_list_reports_declared_image_input(monkeypatch):
    def handle(request):
        assert str(request.url) == "https://api.deepseek.com/models"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "deepseek-flash", "input_modalities": ["text", "image"]},
                    {"id": "text-only", "name": "Text", "input_modalities": ["text"]},
                    {
                        "id": "router/model",
                        "architecture": {"input_modalities": ["image"]},
                    },
                    {"id": "gpt-4o"},
                    {"id": "gpt-4o"},
                    {"object": "model"},
                ],
            },
        )

    _mock_client(monkeypatch, handle)
    models = await list_models(_provider(base_url="https://api.deepseek.com"))
    assert models == (
        ModelInfo("deepseek-flash", "", True),
        ModelInfo("text-only", "Text", False),
        ModelInfo("router/model", "", True),
        ModelInfo("gpt-4o", "", None),
    )


async def test_anthropic_model_list_follows_pages(monkeypatch):
    pages = []

    def handle(request):
        pages.append(dict(request.url.params))
        assert str(request.url).startswith("https://api.anthropic.com/v1/models")
        assert request.headers["anthropic-version"] == "2023-06-01"
        if "after_id" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "claude-a",
                            "display_name": "Claude A",
                            "capabilities": {"image_input": {"supported": True}},
                        }
                    ],
                    "has_more": True,
                    "last_id": "claude-a",
                },
            )
        return httpx.Response(
            200, json={"data": [{"id": "claude-b"}], "has_more": False}
        )

    _mock_client(monkeypatch, handle)
    models = await list_models(_provider("anthropic"))
    assert models == (ModelInfo("claude-a", "Claude A", True), ModelInfo("claude-b"))
    assert pages == [{"limit": "1000"}, {"limit": "1000", "after_id": "claude-a"}]


async def test_malformed_model_list_is_an_error(monkeypatch):
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json=["x"]))
    with pytest.raises(VisionAPIError, match="格式异常"):
        await list_models(_provider())


async def test_deepseek_balance_uses_bearer_over_https_for_any_protocol(monkeypatch):
    def handle(request):
        assert str(request.url) == "https://api.deepseek.com/user/balance"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        assert "x-api-key" not in request.headers
        return httpx.Response(
            200,
            json={
                "is_available": True,
                "balance_infos": [
                    {
                        "currency": "CNY",
                        "total_balance": "110.00",
                        "granted_balance": "10.00",
                        "topped_up_balance": "100.00",
                    },
                    {"currency": "USD", "total_balance": "bad"},
                ],
            },
        )

    _mock_client(monkeypatch, handle)
    # DeepSeek 的 Anthropic 兼容地址与误填的 http:// 也查询同一个官方接口。
    provider = _provider("anthropic", base_url="http://api.deepseek.com/anthropic")
    assert balance_provider(provider) == "DeepSeek"
    result = await query_balance(provider)
    assert result.available is True
    assert result.balances == (
        Balance(
            "CNY",
            "110.00",
            (BalanceItem("赠送余额", "10.00"), BalanceItem("充值余额", "100.00")),
        ),
    )


@pytest.mark.parametrize(
    "host,currency", [("api.moonshot.cn", "CNY"), ("api.moonshot.ai", "USD")]
)
async def test_kimi_balance_reports_currency_by_site(monkeypatch, host, currency):
    def handle(request):
        assert str(request.url) == f"https://{host}/v1/users/me/balance"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "available_balance": 0,
                    "voucher_balance": 46.58893,
                    "cash_balance": -46.58893,
                },
                "status": True,
            },
        )

    _mock_client(monkeypatch, handle)
    result = await query_balance(_provider(base_url=f"https://{host}/v1"))
    assert result.provider == "Kimi"
    assert result.available is False
    assert result.balances == (
        Balance(
            currency,
            "0.00",
            (BalanceItem("代金券余额", "46.59"), BalanceItem("现金余额", "-46.59")),
        ),
    )


async def test_balance_is_refused_without_a_known_api_or_key(monkeypatch):
    def unexpected(request):
        raise AssertionError("no request expected")

    _mock_client(monkeypatch, unexpected)
    assert balance_provider(_provider()) is None
    with pytest.raises(VisionAPIError, match="DeepSeek 与 Kimi"):
        await query_balance(_provider())
    with pytest.raises(VisionAPIError, match="API Key"):
        await query_balance(_provider(base_url="https://api.deepseek.com", api_key=""))


def test_small_supported_images_are_sent_unchanged():
    data = _image("PNG", (64, 64))
    assert prepare_vision_image(data) == VisionImage(
        "image/png", base64.b64encode(data).decode()
    )


@pytest.mark.parametrize(
    "data",
    [
        _image("PNG", (3000, 1000), "RGBA"),
        _image("GIF", (64, 64), "P"),
        _image(
            "WEBP",
            (64, 64),
            save_all=True,
            append_images=[Image.new("RGB", (64, 64), "blue")],
        ),
    ],
    ids=["large-alpha", "gif", "animated-webp"],
)
def test_other_images_become_bounded_first_frame_jpeg(data):
    image = prepare_vision_image(data)
    assert image.media_type == "image/jpeg"
    with Image.open(BytesIO(base64.b64decode(image.data))) as decoded:
        assert decoded.format == "JPEG" and max(decoded.size) <= 2048
        red, green, blue = decoded.convert("RGB").getpixel((0, 0))
        assert red > 200 and green < 60 and blue < 60


def test_oversized_encodings_step_down_until_they_fit(monkeypatch):
    monkeypatch.setattr(vision_image, "MAX_DIRECT_BYTES", 2000)
    monkeypatch.setattr(vision_image, "_RESIZE_STEPS", ((2048, 95), (16, 50)))
    noise = Image.frombytes("RGB", (300, 300), (bytes(range(256)) * 1055)[:270000])
    buffer = BytesIO()
    noise.save(buffer, format="PNG")
    image = prepare_vision_image(buffer.getvalue())
    with Image.open(BytesIO(base64.b64decode(image.data))) as decoded:
        assert (image.media_type, max(decoded.size)) == ("image/jpeg", 16)
    monkeypatch.setattr(vision_image, "_RESIZE_STEPS", ((2048, 95),))
    with pytest.raises(VisionAPIError):
        prepare_vision_image(buffer.getvalue())


def test_unreadable_image_and_generated_sample():
    with pytest.raises(VisionAPIError, match="无法转换"):
        prepare_vision_image(b"not an image")
    sample = sample_image()
    with Image.open(BytesIO(base64.b64decode(sample.data))) as decoded:
        assert (sample.media_type, decoded.format, decoded.size) == (
            "image/png",
            "PNG",
            (256, 256),
        )
