"""Present provenance evidence without equating missing signals with human authorship."""

from collections.abc import Sequence
from dataclasses import dataclass

from .c2pa_check import C2PAResult

OPENAI_KINDS = frozenset({"c2pa", "synthid"})


@dataclass(frozen=True)
class VisionResult:
    """One vision model's outcome; an empty verdict means it did not finish."""

    name: str
    verdict: str = ""
    confidence: int | None = None
    reason: str = ""
    error: str = ""


_VERDICT_LABELS = {
    "ai": "倾向 AI 生成",
    "not_ai": "倾向非 AI 生成",
    "uncertain": "无法判断",
}


def _vision_lines(vision: Sequence[VisionResult]) -> list[str]:
    lines = ["视觉模型（仅供参考）："]
    for result in vision:
        if not result.verdict:
            lines.append(f"· {result.name}：未完成，{result.error}")
            continue
        text = _VERDICT_LABELS[result.verdict]
        if result.confidence is not None:
            text += f"（置信度 {result.confidence}%）"
        if result.reason:
            text += f"，{result.reason}"
        lines.append(f"· {result.name}：{text}")
    return lines


def _vision_conclusion(vision: Sequence[VisionResult], prefix: str) -> str:
    answered = [result for result in vision if result.verdict]
    if not answered:
        return "结论：无法判断是否为 AI 图片。"
    total = len(answered)
    ai = sum(result.verdict == "ai" for result in answered)
    not_ai = sum(result.verdict == "not_ai" for result in answered)
    if ai * 2 > total:
        return f"结论：{prefix}{ai}/{total} 个视觉模型倾向 AI 生成，仅供参考。"
    if not_ai * 2 > total:
        return f"结论：{prefix}{not_ai}/{total} 个视觉模型倾向非 AI 生成，仅供参考，不能证明非 AI。"
    if ai and not_ai:
        return f"结论：{prefix}视觉模型意见不一致，无法判断是否为 AI 图片。"
    return f"结论：{prefix}无法判断是否为 AI 图片。"


def build_report(
    local: C2PAResult | None,
    remote: dict[str, dict] | None,
    remote_error: str = "",
    *,
    openai_kinds: frozenset[str] = OPENAI_KINDS,
    vision: Sequence[VisionResult] = (),
) -> str:
    """Disabled sources (local=None, kinds not listed) are omitted from the reply."""
    lines = ["图片 AI 检测"]
    local_positive = False
    if local is not None:
        local_status = {
            "absent": "未检出嵌入式凭证",
            "remote": "发现远程凭证引用，未联网获取，无法校验",
            "unreadable": "无法读取或校验，不能视为未检出",
        }
        local_positive = local.ai_declared and local.validation_state == "Trusted"
        if local.status == "present":
            validation = {
                "Trusted": "校验通过，签名来源受信任",
                "Valid": "完整性校验通过，签名来源未受信任",
                "Invalid": "校验失败，不能采信其中声明",
            }.get(local.validation_state, "校验状态未知，不能确认来源")
            declaration = (
                "含 AI 生成/编辑声明"
                if local.ai_declared
                else "未发现 AI 生成/编辑声明"
            )
            lines.append(f"本地 C2PA：已检出，{declaration}；{validation}。")
        else:
            lines.append(f"本地 C2PA：{local_status[local.status]}。")
    remote_positive = False
    remote_claim = False
    if openai_kinds and remote is not None:
        if "c2pa" in openai_kinds:
            c2pa = remote["c2pa"]
            state = {
                "trusted": "受信任",
                "valid": "有效但来源未受信任",
                "invalid": "校验失败",
                "not_present": "无凭证",
            }[c2pa["validation_state"]]
            remote_claim = c2pa["outcome"] == "detected"
            lines.append(
                f"OpenAI C2PA：{'检出 OpenAI AI 生成凭证' if remote_claim else '未检出 OpenAI AI 生成凭证'}（{state}）。"
            )
            if c2pa.get("issuer"):
                lines.append(f"凭证签发者：{str(c2pa['issuer'])[:100]}")
            remote_positive = remote_claim and c2pa["validation_state"] == "trusted"
        if "synthid" in openai_kinds:
            synthid_detected = remote["synthid"]["outcome"] == "detected"
            lines.append(
                f"SynthID（OpenAI）：{'检出水印' if synthid_detected else '未检出水印'}。"
            )
            remote_positive = remote_positive or synthid_detected
    elif openai_kinds:
        label = {
            frozenset({"c2pa"}): "OpenAI C2PA",
            frozenset({"synthid"}): "SynthID（OpenAI）",
        }.get(openai_kinds, "OpenAI C2PA / SynthID")
        lines.append(
            f"{label}：未完成检测。{remote_error or '管理员尚未配置检测密钥。'}"
        )
    if vision:
        lines.extend(_vision_lines(vision))

    if local_positive or remote_positive:
        lines.append("结论：检测到 AI 生成/编辑的来源证据。")
    elif (local is not None and local.ai_declared) or remote_claim:
        lines.append("结论：存在 AI 相关声明，但凭证未获信任或校验失败，无法确认。")
    else:
        checked = local is not None or (bool(openai_kinds) and remote is not None)
        lines.append(
            _vision_conclusion(vision, "未发现可确认的来源证据；" if checked else "")
        )

    notes = []
    if openai_kinds:
        notes.append("OpenAI 接口仅识别其支持的来源信号")
    if local is not None or openai_kinds:
        notes.append("未检出不代表非 AI")
    if vision:
        notes.append("视觉模型仅根据画面推测，可能误判，不能作为来源证据")
    notes.append("QQ 压缩、截图或转存可能丢失元数据或削弱水印，请尽量使用原图")
    lines.append("；".join(notes) + "。")
    return "\n".join(lines)
