"""出站代理：多个代理存于 SystemSetting JSON，密码逐条加密；各功能按 id 选用。"""

from __future__ import annotations

import json
import secrets
import unicodedata
from dataclasses import dataclass, field

from nonebot.log import logger

from shared.config.proxy import ProxyConfig
from shared.security.crypto import decrypt_value, encrypt_value

PROXIES_KEY = "proxies"
X_PROXY_KEY = "x_proxy_id"
AI_IMAGE_OPENAI_PROXY_KEY = "ai_image_openai_proxy_id"
# 选用代理的设置项及其在提示中的名称；视觉模型的代理记录在各自的配置里。
FEATURE_PROXY_KEYS = {
    X_PROXY_KEY: "X（推文订阅、链接解析）",
    AI_IMAGE_OPENAI_PROXY_KEY: "AI 图片检测的 OpenAI 来源检测",
}
PROXY_SCHEMES = ("http", "https", "socks5")
MAX_PROXY_NAME_LENGTH = 32
MAX_HOST_LENGTH = 255
MAX_USERNAME_LENGTH = 128
MAX_PASSWORD_LENGTH = 256


@dataclass(frozen=True)
class ProxyRecord:
    id: str
    name: str
    scheme: str
    host: str
    port: int
    username: str = ""
    password: str = field(default="", repr=False)
    password_set: bool = False

    def to_config(self) -> ProxyConfig:
        return ProxyConfig(
            enabled=True,
            scheme=self.scheme,
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        )


def _valid_port(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value < 65536


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
            and isinstance(item.get("name"), str)
            and item.get("scheme") in PROXY_SCHEMES
            and isinstance(item.get("host"), str)
            and item["host"]
            and _valid_port(item.get("port"))
            and isinstance(item.get("username", ""), str)
            and isinstance(item.get("password_encrypted", ""), str)
        ):
            entries.append(item)
    return entries


class ProxyInUseError(ValueError):
    """Deleting would silently switch features to direct connections."""


def proxy_ids(raw: str | None) -> frozenset[str]:
    return frozenset(entry["id"] for entry in _stored_entries(raw))


def load_proxies(raw: str | None) -> tuple[ProxyRecord, ...]:
    records = []
    for item in _stored_entries(raw):
        encrypted = item.get("password_encrypted", "")
        password = ""
        if encrypted:
            try:
                password = decrypt_value(encrypted)
            except ValueError:
                logger.error("代理「{}」的密码解密失败", item["name"])
        records.append(
            ProxyRecord(
                id=item["id"],
                name=item["name"],
                scheme=item["scheme"],
                host=item["host"],
                port=item["port"],
                username=item.get("username", ""),
                password=password,
                password_set=bool(encrypted),
            )
        )
    return tuple(records)


def proxies_for_api(records: tuple[ProxyRecord, ...]) -> list[dict]:
    return [
        {
            "id": record.id,
            "name": record.name,
            "scheme": record.scheme,
            "host": record.host,
            "port": record.port,
            "username": record.username,
            "password_configured": record.password_set,
        }
        for record in records
    ]


def resolve_proxy(records: tuple[ProxyRecord, ...], proxy_id: str) -> ProxyConfig:
    """Proxy for a feature; empty or unknown ids connect directly (disabled config)."""
    record = next((row for row in records if row.id == proxy_id), None)
    return record.to_config() if proxy_id and record is not None else ProxyConfig()


def _has_control_chars(text: str) -> bool:
    return any(unicodedata.category(char).startswith("C") for char in text)


def _clean_name(raw: object) -> str:
    name = str(raw or "").strip()
    if not name:
        raise ValueError("代理名称不能为空")
    if len(name) > MAX_PROXY_NAME_LENGTH or _has_control_chars(name):
        raise ValueError(
            f"代理名称不能超过 {MAX_PROXY_NAME_LENGTH} 个字符或包含控制字符"
        )
    return name


def _clean_host(raw: object) -> str:
    host = str(raw or "").strip()
    if not host:
        raise ValueError("请填写代理主机")
    if (
        len(host) > MAX_HOST_LENGTH
        or any(char.isspace() or char in "/@?#" for char in host)
        or _has_control_chars(host)
    ):
        raise ValueError("代理主机只填写域名或 IP，不要包含协议、路径、账号或空白字符")
    if ":" in host and not (host.startswith("[") and host.endswith("]")):
        raise ValueError("IPv6 地址请加方括号，例如 [::1]；端口单独填写")
    return host


def _clean_port(raw: object) -> int:
    if not _valid_port(raw):
        raise ValueError("代理端口须在 1–65535 之间")
    return raw


def _clean_credential(raw: object, label: str, max_length: int) -> str:
    text = str(raw or "")
    if len(text) > max_length or _has_control_chars(text):
        raise ValueError(f"代理{label}不能超过 {max_length} 个字符或包含控制字符")
    return text


def _entry_fields(entry: dict) -> dict:
    return {
        "name": entry["name"],
        "scheme": entry["scheme"],
        "host": entry["host"],
        "port": entry["port"],
        "username": entry.get("username", ""),
    }


def _host_changed(previous_host: str, host: str) -> bool:
    return previous_host.lower() != host.lower()


def apply_proxy(
    stored_raw: str | None, proxy_id: str | None, changes: dict
) -> tuple[str, str]:
    """Create (``proxy_id`` is None) or partially update one proxy.

    返回 (要保存的 JSON, 代理 id)。``changes`` 不含 password 时保留已存密码，但主机
    变化后必须重新填写，避免把已保存但不可读回的密码发往新的主机。代理不存在时抛出
    KeyError。
    """
    entries = _stored_entries(stored_raw)
    previous = None
    if proxy_id is not None:
        previous = next((row for row in entries if row["id"] == proxy_id), None)
        if previous is None:
            raise KeyError(proxy_id)
    fields = {**(_entry_fields(previous) if previous else {}), **changes}
    name = _clean_name(fields.get("name"))
    if any(
        row is not previous and row["name"].casefold() == name.casefold()
        for row in entries
    ):
        raise ValueError(f"代理名称「{name}」已被使用")
    scheme = str(fields.get("scheme") or "").strip().lower()
    if scheme not in PROXY_SCHEMES:
        raise ValueError("代理协议仅支持 HTTP、HTTPS 或 SOCKS5")
    host = _clean_host(fields.get("host"))
    port = _clean_port(fields.get("port"))
    username = _clean_credential(
        fields.get("username"), "用户名", MAX_USERNAME_LENGTH
    ).strip()

    password = changes.get("password")
    if password is None:
        encrypted = previous.get("password_encrypted", "") if previous else ""
        if encrypted and _host_changed(previous["host"], host):
            raise ValueError(f"修改「{name}」的主机后，需要重新填写密码")
    else:
        text = _clean_credential(password, "密码", MAX_PASSWORD_LENGTH)
        encrypted = encrypt_value(text) if text else ""

    if previous is not None:
        saved_id = previous["id"]
    else:
        saved_id = secrets.token_hex(6)
        while any(row["id"] == saved_id for row in entries):
            saved_id = secrets.token_hex(6)
    entry = {
        "id": saved_id,
        "name": name,
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password_encrypted": encrypted,
    }
    updated = [entry if row is previous else row for row in entries]
    if previous is None:
        updated.append(entry)
    return json.dumps(updated, ensure_ascii=False), saved_id


def drop_proxy(stored_raw: str | None, proxy_id: str) -> str:
    entries = _stored_entries(stored_raw)
    remaining = [row for row in entries if row["id"] != proxy_id]
    if len(remaining) == len(entries):
        raise KeyError(proxy_id)
    return json.dumps(remaining, ensure_ascii=False)


def probe_proxy(
    records: tuple[ProxyRecord, ...],
    *,
    proxy_id: str | None,
    scheme: str,
    host: object,
    port: object,
    username: object = "",
    password: str | None = None,
) -> ProxyConfig:
    """Build a proxy from unsaved form values for 测试连接, with the saving rules."""
    previous = None
    if proxy_id:
        previous = next((row for row in records if row.id == proxy_id), None)
        if previous is None:
            raise ValueError("代理列表已变化，请刷新页面后重试")
    scheme = str(scheme or "").strip().lower()
    if scheme not in PROXY_SCHEMES:
        raise ValueError("代理协议仅支持 HTTP、HTTPS 或 SOCKS5")
    clean_host = _clean_host(host)
    if password is None:
        if (
            previous is not None
            and previous.password_set
            and _host_changed(previous.host, clean_host)
        ):
            raise ValueError("修改主机后，需要重新填写密码")
        secret = previous.password if previous is not None else ""
    else:
        secret = _clean_credential(password, "密码", MAX_PASSWORD_LENGTH)
    return ProxyConfig(
        enabled=True,
        scheme=scheme,
        host=clean_host,
        port=_clean_port(port),
        username=_clean_credential(username, "用户名", MAX_USERNAME_LENGTH).strip(),
        password=secret,
    )
