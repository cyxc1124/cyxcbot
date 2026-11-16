"""AI 图片检测的视觉模型供应商：JSON 存于 SystemSetting，API Key 逐条加密。"""

from __future__ import annotations

import hashlib
import json
import secrets
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from nonebot.log import logger

from shared.security.crypto import decrypt_value, encrypt_value

if TYPE_CHECKING:
    from shared.config.types import AppConfigSnapshot

VISION_PROVIDERS_KEY = "ai_image_vision_providers"
VISION_API_TYPES = ("openai", "anthropic")
# 沿用两家官方 SDK 的 base_url 约定，便于直接照抄供应商文档中的地址。
DEFAULT_VISION_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}
MAX_PROVIDER_NAME_LENGTH = 32
MAX_MODEL_LENGTH = 128
MAX_BASE_URL_LENGTH = 256
MAX_API_KEY_LENGTH = 512
# 回复格式变化时递增，让已缓存的旧格式结果重新检测。
REPORT_VERSION = 1
# 检测缓存最多保留的未修改记录条数（Web Admin 可改）。
CACHE_MAX_ENTRIES_DEFAULT = 500
CACHE_MAX_ENTRIES_LIMIT = 10000


@dataclass(frozen=True)
class VisionProviderRecord:
    id: str
    name: str
    api_type: str
    model: str
    base_url: str = ""
    enabled: bool = True
    # 引用「系统 → 网络代理」中的代理 id，空字符串表示直接连接。
    proxy_id: str = ""
    api_key: str = field(default="", repr=False)
    api_key_set: bool = False

    @property
    def endpoint(self) -> str:
        """Base URL actually requested; an empty setting means the official API."""
        return _endpoint(self.api_type, self.base_url)


def _endpoint(api_type: str, base_url: str) -> str:
    return base_url or DEFAULT_VISION_BASE_URLS[api_type]


def _stored_entries(raw: str | None) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    entries: list[dict] = []
    for item in data:
        if (
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"]
            and all(entry["id"] != item["id"] for entry in entries)
            and item.get("api_type") in VISION_API_TYPES
            and isinstance(item.get("name"), str)
            and isinstance(item.get("model"), str)
            and isinstance(item.get("base_url", ""), str)
            and isinstance(item.get("api_key_encrypted", ""), str)
            and isinstance(item.get("proxy_id", ""), str)
        ):
            entries.append(item)
    return entries


def load_vision_providers(raw: str | None) -> tuple[VisionProviderRecord, ...]:
    records = []
    for item in _stored_entries(raw):
        encrypted = item.get("api_key_encrypted", "")
        api_key = ""
        if encrypted:
            try:
                api_key = decrypt_value(encrypted)
            except ValueError:
                logger.error(
                    "AI 图片检测视觉模型「{}」的 API Key 解密失败", item["name"]
                )
        records.append(
            VisionProviderRecord(
                id=item["id"],
                name=item["name"],
                api_type=item["api_type"],
                model=item["model"],
                base_url=item.get("base_url", ""),
                enabled=bool(item.get("enabled", True)),
                proxy_id=item.get("proxy_id", ""),
                api_key=api_key,
                api_key_set=bool(encrypted),
            )
        )
    return tuple(records)


def vision_providers_for_api(records: tuple[VisionProviderRecord, ...]) -> list[dict]:
    return [
        {
            "id": record.id,
            "name": record.name,
            "api_type": record.api_type,
            "base_url": record.base_url,
            "model": record.model,
            "enabled": record.enabled,
            "proxy_id": record.proxy_id,
            "api_key_configured": record.api_key_set,
        }
        for record in records
    ]


def _has_control_chars(text: str) -> bool:
    return any(unicodedata.category(char).startswith("C") for char in text)


def _clean_text(value: object, label: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > max_length:
        raise ValueError(f"{label}不能超过 {max_length} 个字符")
    if _has_control_chars(text):
        raise ValueError(f"{label}不能包含控制字符")
    return text


def normalize_base_url(raw: object) -> str:
    """Validate an http(s) base URL; empty means the official endpoint."""
    text = str(raw or "").strip()
    if not text:
        return ""
    error = "接口地址须为 http:// 或 https:// 开头的完整地址，不能包含账号、查询参数或空白字符"
    if len(text) > MAX_BASE_URL_LENGTH:
        raise ValueError(f"接口地址不能超过 {MAX_BASE_URL_LENGTH} 个字符")
    try:
        parts = urlsplit(text)
        invalid = (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.port == 0
            or parts.username is not None
            or parts.password is not None
            or bool(parts.query)
            or bool(parts.fragment)
            or any(char.isspace() for char in text)
            or _has_control_chars(text)
        )
    except ValueError:
        raise ValueError(error) from None
    if invalid:
        raise ValueError(error)
    return text.rstrip("/")


def _endpoint_changed(
    previous_type: str, previous_base: str, api_type: str, base_url: str
) -> bool:
    return previous_type != api_type or _endpoint(
        previous_type, previous_base
    ) != _endpoint(api_type, base_url)


def _clean_key(raw: object, label: str) -> str:
    key = str(raw).strip()
    if len(key) > MAX_API_KEY_LENGTH or any(
        ord(char) < 33 or ord(char) > 126 for char in key
    ):
        raise ValueError(f"{label}不得含空白或非 ASCII 字符")
    return key


def _clean_model(raw: object, label: str) -> str:
    model = _clean_text(raw, label, MAX_MODEL_LENGTH)
    if any(char.isspace() for char in model):
        raise ValueError(f"{label}不能包含空白字符")
    return model


def _entry_fields(entry: dict) -> dict:
    return {
        "name": entry["name"],
        "api_type": entry["api_type"],
        "base_url": entry.get("base_url", ""),
        "model": entry["model"],
        "enabled": bool(entry.get("enabled", True)),
        "proxy_id": entry.get("proxy_id", ""),
    }


def apply_vision_provider(
    stored_raw: str | None,
    provider_id: str | None,
    changes: dict,
    proxy_ids: frozenset[str] = frozenset(),
) -> tuple[str, str]:
    """Create (``provider_id`` is None) or partially update one provider.

    返回 (要保存的 JSON, 供应商 id)；其他供应商原样保留。``changes`` 不含 api_key
    时保留已存密钥，但接口类型或地址变化后必须重新填写，避免把已保存但不可读回的
    密钥发往新的地址。供应商不存在时抛出 KeyError。
    """
    entries = _stored_entries(stored_raw)
    previous = None
    if provider_id is not None:
        previous = next((row for row in entries if row["id"] == provider_id), None)
        if previous is None:
            raise KeyError(provider_id)
    fields = {**(_entry_fields(previous) if previous else {}), **changes}
    name = _clean_text(fields.get("name"), "视觉模型名称", MAX_PROVIDER_NAME_LENGTH)
    if any(
        row is not previous and row["name"].casefold() == name.casefold()
        for row in entries
    ):
        raise ValueError(f"视觉模型名称「{name}」已被使用")
    api_type = fields.get("api_type")
    if api_type not in VISION_API_TYPES:
        raise ValueError("接口类型仅支持 OpenAI 或 Anthropic")
    model = _clean_model(fields.get("model"), f"「{name}」的模型")
    base_url = normalize_base_url(fields.get("base_url"))
    proxy_id = str(fields.get("proxy_id") or "")
    if "proxy_id" in changes and proxy_id and proxy_id not in proxy_ids:
        raise ValueError(f"「{name}」选择的代理不存在，请刷新页面后重新选择")

    api_key = changes.get("api_key")
    if api_key is None:
        encrypted = previous.get("api_key_encrypted", "") if previous else ""
        if encrypted and _endpoint_changed(
            previous["api_type"], previous.get("base_url", ""), api_type, base_url
        ):
            raise ValueError(f"修改「{name}」的接口类型或地址后，需要重新填写 API Key")
    else:
        key = _clean_key(api_key, f"「{name}」的 API Key")
        encrypted = encrypt_value(key) if key else ""

    if previous is not None:
        saved_id = previous["id"]
    else:
        saved_id = secrets.token_hex(6)
        while any(row["id"] == saved_id for row in entries):
            saved_id = secrets.token_hex(6)
    entry = {
        "id": saved_id,
        "name": name,
        "api_type": api_type,
        "base_url": base_url,
        "model": model,
        "enabled": bool(fields.get("enabled", True)),
        "proxy_id": proxy_id,
        "api_key_encrypted": encrypted,
    }
    updated = [entry if row is previous else row for row in entries]
    if previous is None:
        updated.append(entry)
    return json.dumps(updated, ensure_ascii=False), saved_id


def drop_vision_provider(stored_raw: str | None, provider_id: str) -> str:
    entries = _stored_entries(stored_raw)
    remaining = [row for row in entries if row["id"] != provider_id]
    if len(remaining) == len(entries):
        raise KeyError(provider_id)
    return json.dumps(remaining, ensure_ascii=False)


def probe_provider(
    records: tuple[VisionProviderRecord, ...],
    *,
    provider_id: str | None,
    api_type: str,
    base_url: object = "",
    model: object = "",
    proxy_id: str = "",
    api_key: str | None = None,
    require_model: bool = False,
) -> VisionProviderRecord:
    """Build a temporary record for 获取模型 / 测试 / 余额 from unsaved form values.

    沿用保存时的规则：未重新填写密钥时只能把已存密钥发往原地址。
    """
    if api_type not in VISION_API_TYPES:
        raise ValueError("接口类型仅支持 OpenAI 或 Anthropic")
    base = normalize_base_url(base_url)
    previous = None
    if provider_id:
        previous = next((row for row in records if row.id == provider_id), None)
        if previous is None:
            raise ValueError("视觉模型列表已变化，请刷新页面后重试")
    if api_key is None:
        if (
            previous is not None
            and previous.api_key_set
            and _endpoint_changed(previous.api_type, previous.base_url, api_type, base)
        ):
            raise ValueError("修改接口类型或地址后，需要重新填写 API Key")
        key = previous.api_key if previous is not None else ""
    else:
        key = _clean_key(api_key, "API Key")
    model_text = str(model or "").strip()
    if require_model or model_text:
        model_text = _clean_model(model_text, "模型")
    return VisionProviderRecord(
        id=provider_id or "",
        name=previous.name if previous is not None else "",
        api_type=api_type,
        model=model_text,
        base_url=base,
        proxy_id=proxy_id,
        api_key=key,
        api_key_set=bool(key),
    )


def detection_fingerprint(snapshot: AppConfigSnapshot) -> str:
    """Hash of everything that shapes a detection reply; cached replies must match it."""
    setup = {
        "version": REPORT_VERSION,
        "local_c2pa": snapshot.ai_image_local_c2pa_enabled,
        "openai_c2pa": snapshot.ai_image_openai_c2pa_enabled,
        "openai_synthid": snapshot.ai_image_openai_synthid_enabled,
        "openai_key": bool(snapshot.ai_image_openai_api_key),
        "vision": [
            [provider.name, provider.api_type, provider.endpoint, provider.model]
            for provider in snapshot.ai_image_vision_providers
            if provider.enabled
        ],
    }
    encoded = json.dumps(setup, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
