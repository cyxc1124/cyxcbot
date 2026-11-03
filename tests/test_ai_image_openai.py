"""The API uses the original image once and refuses incomplete or contradictory results."""

from copy import deepcopy

import ai_image_helpers  # noqa: F401
import httpx
import pytest

from plugins.ai_image_detector import openai_check
from plugins.ai_image_detector.c2pa_check import C2PAResult
from plugins.ai_image_detector.image import ImageDetectionError
from plugins.ai_image_detector.report import build_report

PAYLOAD = {
    "object": "content_provenance_check",
    "created_at": 1,
    "results": [
        {
            "type": "c2pa",
            "outcome": "not_detected",
            "validation_state": "not_present",
            "issuer": None,
        },
        {"type": "synthid", "outcome": "detected"},
    ],
}


async def test_api_multipart_upload_preserves_bytes_and_only_calls_once(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/content_provenance_checks"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        assert "multipart/form-data; boundary=" in request.headers["Content-Type"]
        assert b"original-image-with-metadata" in request.content
        assert b"image/png" in request.content
        return httpx.Response(200, json=PAYLOAD)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(openai_check.httpx, "AsyncClient", lambda **kwargs: client)
    result = await openai_check.check_openai(
        b"original-image-with-metadata", "image/png", "test-only-key"
    )
    assert result["synthid"]["outcome"] == "detected"
    assert len(calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 302])
async def test_http_errors_are_not_negative_detections(monkeypatch, status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, json={"error": {"message": "sensitive-upstream-details"}}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(openai_check.httpx, "AsyncClient", lambda **kwargs: client)
    with pytest.raises(ImageDetectionError) as error:
        await openai_check.check_openai(b"image", "image/png", "test-only-key")
    assert "sensitive-upstream-details" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload", [None, {}, {"object": "content_provenance_check", "results": []}]
)
def test_incomplete_responses_do_not_become_not_detected(payload):
    with pytest.raises(ImageDetectionError):
        openai_check.parse_result(payload)


def test_invalid_manifest_cannot_be_positive():
    payload = deepcopy(PAYLOAD)
    payload["results"][0].update(outcome="detected", validation_state="invalid")
    with pytest.raises(ImageDetectionError, match="矛盾"):
        openai_check.parse_result(payload)


@pytest.mark.parametrize("state", ["Valid", "Invalid", "Unknown"])
def test_untrusted_local_ai_claim_is_inconclusive(state):
    report = build_report(C2PAResult("present", True, state), None)
    assert "无法确认" in report
    assert "检测到 AI 生成/编辑的来源证据" not in report
    assert "未完成检测" in report


def test_no_evidence_never_means_human_created():
    payload = deepcopy(PAYLOAD)
    payload["results"][1]["outcome"] = "not_detected"
    report = build_report(C2PAResult("absent"), openai_check.parse_result(payload))
    assert "无法判断是否为 AI 图片" in report
    assert "未检出不代表非 AI" in report


def test_synthid_detection_is_positive_with_openai_scope():
    report = build_report(C2PAResult("absent"), openai_check.parse_result(PAYLOAD))
    assert "SynthID（OpenAI）：检出水印" in report
    assert "检测到 AI 生成/编辑的来源证据" in report


def test_external_failure_is_not_an_absent_watermark():
    report = build_report(C2PAResult("present", True, "Valid"), None, "请求受限")
    assert "请求受限" in report
    assert "未检出水印" not in report
