"""Use OpenAI's documented verifier; it only recognizes supported OpenAI signals."""

import httpx

from shared.config.proxy import ProxyConfig

from .image import ImageDetectionError

_ENDPOINT = "https://api.openai.com/v1/content_provenance_checks"


def parse_result(payload: object) -> dict[str, dict]:
    if (
        not isinstance(payload, dict)
        or payload.get("object") != "content_provenance_check"
    ):
        raise ImageDetectionError("OpenAI 检测结果格式异常，未能完成外部检测。")
    entries = payload.get("results")
    if not isinstance(entries, list):
        raise ImageDetectionError("OpenAI 检测结果不完整，未能完成外部检测。")
    results = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") not in ("c2pa", "synthid"):
            continue
        kind = entry["type"]
        if kind in results or entry.get("outcome") not in ("detected", "not_detected"):
            raise ImageDetectionError("OpenAI 检测结果格式异常，未能完成外部检测。")
        results[kind] = entry
    if set(results) != {"c2pa", "synthid"}:
        raise ImageDetectionError("OpenAI 检测结果不完整，未能完成外部检测。")
    c2pa = results["c2pa"]
    if c2pa.get("validation_state") not in (
        "trusted",
        "valid",
        "invalid",
        "not_present",
    ):
        raise ImageDetectionError("OpenAI C2PA 校验状态异常，未能完成外部检测。")
    if c2pa["outcome"] == "detected" and c2pa["validation_state"] not in {
        "trusted",
        "valid",
    }:
        raise ImageDetectionError("OpenAI C2PA 结果矛盾，不能据此判断图片来源。")
    return results


async def check_openai(
    data: bytes, media_type: str, api_key: str, *, proxy: ProxyConfig | None = None
) -> dict[str, dict]:
    extension = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }[media_type]
    try:
        async with httpx.AsyncClient(
            timeout=45,
            follow_redirects=False,
            proxy=proxy.to_url() if proxy else None,
        ) as client:
            response = await client.post(
                _ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (f"image.{extension}", data, media_type)},
            )
    except httpx.HTTPError:
        raise ImageDetectionError(
            "OpenAI 检测连接失败或超时，外部检测未完成。"
        ) from None
    if response.status_code != 200:
        message = {
            400: "OpenAI 无法检测此图片，文件可能不受支持或被拒绝。",
            401: "OpenAI API Key 无效，请管理员检查检测配置。",
            403: "OpenAI 账号没有内容溯源检测权限。",
            404: "OpenAI 账号没有内容溯源检测权限或接口不可用。",
            429: "OpenAI 检测请求受限，请稍后重试。",
        }.get(response.status_code, "OpenAI 检测服务暂不可用，外部检测未完成。")
        raise ImageDetectionError(message)
    try:
        return parse_result(response.json())
    except ValueError as exc:
        if isinstance(exc, ImageDetectionError):
            raise
        raise ImageDetectionError(
            "OpenAI 返回了无法读取的结果，外部检测未完成。"
        ) from None
