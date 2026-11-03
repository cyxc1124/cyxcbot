"""Present provenance evidence without equating missing signals with human authorship."""

from .c2pa_check import C2PAResult


def build_report(
    local: C2PAResult, remote: dict[str, dict] | None, remote_error: str = ""
) -> str:
    lines = ["图片 AI 检测"]
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
            "含 AI 生成/编辑声明" if local.ai_declared else "未发现 AI 生成/编辑声明"
        )
        lines.append(f"本地 C2PA：已检出，{declaration}；{validation}。")
    else:
        lines.append(f"本地 C2PA：{local_status[local.status]}。")
    remote_positive = False
    if remote is not None:
        c2pa = remote["c2pa"]
        synthid = remote["synthid"]
        state = {
            "trusted": "受信任",
            "valid": "有效但来源未受信任",
            "invalid": "校验失败",
            "not_present": "无凭证",
        }[c2pa["validation_state"]]
        c2pa_detected = c2pa["outcome"] == "detected"
        synthid_detected = synthid["outcome"] == "detected"
        lines.append(
            f"OpenAI C2PA：{'检出 OpenAI AI 生成凭证' if c2pa_detected else '未检出 OpenAI AI 生成凭证'}（{state}）。"
        )
        if c2pa.get("issuer"):
            lines.append(f"凭证签发者：{str(c2pa['issuer'])[:100]}")
        lines.append(
            f"SynthID（OpenAI）：{'检出水印' if synthid_detected else '未检出水印'}。"
        )
        remote_positive = synthid_detected or (
            c2pa_detected and c2pa["validation_state"] == "trusted"
        )
    else:
        lines.append(
            f"OpenAI C2PA / SynthID：未完成检测。{remote_error or '管理员尚未配置检测密钥。'}"
        )
    if local_positive or remote_positive:
        lines.append("结论：检测到 AI 生成/编辑的来源证据。")
    elif local.ai_declared or (remote and remote["c2pa"]["outcome"] == "detected"):
        lines.append("结论：存在 AI 相关声明，但凭证未获信任或校验失败，无法确认。")
    else:
        lines.append("结论：无法判断是否为 AI 图片。")
    lines.append(
        "OpenAI 接口仅识别其支持的来源信号；未检出不代表非 AI。QQ 压缩、截图或转存可能丢失元数据或削弱水印，请尽量使用原图。"
    )
    return "\n".join(lines)
