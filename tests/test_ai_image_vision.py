"""Vision model votes are reported as reference only; stored providers load safely."""

import json

import ai_image_helpers  # noqa: F401

from plugins.ai_image_detector.c2pa_check import C2PAResult
from plugins.ai_image_detector.report import VisionResult, build_report
from shared.config.ai_image import load_vision_providers


def test_vision_majority_is_reference_only():
    votes = [
        VisionResult("A", "ai"),
        VisionResult("B", "ai", 90, "纹理异常"),
        VisionResult("C", "not_ai"),
        VisionResult("D", error="请求受限，请稍后重试。"),
    ]
    report = build_report(
        C2PAResult("absent"), None, openai_kinds=frozenset(), vision=votes
    )
    assert "· B：倾向 AI 生成（置信度 90%），纹理异常" in report
    assert "· D：未完成，请求受限，请稍后重试。" in report
    assert (
        "结论：未发现可确认的来源证据；2/3 个视觉模型倾向 AI 生成，仅供参考。" in report
    )
    assert "可能误判" in report
    assert "OpenAI" not in report


def test_negative_or_split_votes_never_prove_human_creation():
    negative = build_report(
        C2PAResult("absent"),
        None,
        openai_kinds=frozenset(),
        vision=[
            VisionResult("A", "not_ai"),
            VisionResult("B", "not_ai"),
            VisionResult("C", "uncertain"),
        ],
    )
    assert "2/3 个视觉模型倾向非 AI 生成，仅供参考，不能证明非 AI" in negative
    split = build_report(
        None,
        None,
        openai_kinds=frozenset(),
        vision=[VisionResult("A", "ai"), VisionResult("B", "not_ai")],
    )
    assert "结论：视觉模型意见不一致，无法判断是否为 AI 图片。" in split
    assert "本地 C2PA" not in split


def test_trusted_provenance_outranks_vision_votes():
    report = build_report(
        C2PAResult("present", True, "Trusted"),
        None,
        openai_kinds=frozenset(),
        vision=[VisionResult("A", "not_ai")],
    )
    assert "结论：检测到 AI 生成/编辑的来源证据。" in report


def test_corrupt_stored_providers_do_not_break_loading():
    raw = json.dumps(
        [
            {
                "id": "a",
                "name": "A",
                "api_type": "openai",
                "model": "m",
                "api_key_encrypted": "not-a-token",
            },
            {"id": "a", "name": "重复", "api_type": "openai", "model": "m"},
            {"id": "b", "name": "B", "api_type": "unknown", "model": "m"},
            "junk",
        ]
    )
    (record,) = load_vision_providers(raw)
    assert (record.name, record.api_key, record.api_key_set) == ("A", "", True)
    assert record.endpoint == "https://api.openai.com/v1"
    assert load_vision_providers("not json") == ()
