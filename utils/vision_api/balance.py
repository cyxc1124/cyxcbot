"""Account balance for providers whose inference API key can read it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from shared.config.ai_image import VisionProviderRecord
from shared.config.proxy import ProxyConfig

from .client import VisionAPIError, request_json

# host -> (名称, 路径, 解析方式, 币种)。只收录官方文档写明可用普通 API Key 查询的接口；
# 需与 web/src/pages/settings/aiImageVisionForm.ts 的 BALANCE_PROVIDERS 保持一致。
_BALANCE_APIS = {
    "api.deepseek.com": ("DeepSeek", "/user/balance", "deepseek", ""),
    "api.moonshot.cn": ("Kimi", "/v1/users/me/balance", "kimi", "CNY"),
    "api.moonshot.ai": ("Kimi", "/v1/users/me/balance", "kimi", "USD"),
}
_DECIMAL = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class BalanceItem:
    label: str
    amount: str


@dataclass(frozen=True)
class Balance:
    currency: str
    total: str
    items: tuple[BalanceItem, ...] = ()


@dataclass(frozen=True)
class BalanceResult:
    provider: str
    # None 表示接口未说明是否还能调用。
    available: bool | None
    balances: tuple[Balance, ...]


def _host(provider: VisionProviderRecord) -> str:
    return (urlsplit(provider.endpoint).hostname or "").lower()


def balance_provider(provider: VisionProviderRecord) -> str | None:
    entry = _BALANCE_APIS.get(_host(provider))
    return entry[0] if entry else None


def _amount(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return f"{value:.2f}"
    if isinstance(value, str) and _DECIMAL.fullmatch(value.strip()):
        return value.strip()
    return None


def _items(data: dict, fields: tuple[tuple[str, str], ...]) -> tuple[BalanceItem, ...]:
    return tuple(
        BalanceItem(label, amount)
        for label, key in fields
        if (amount := _amount(data.get(key))) is not None
    )


def _parse_deepseek(name: str, payload: object) -> BalanceResult:
    infos = payload.get("balance_infos") if isinstance(payload, dict) else None
    if not isinstance(infos, list):
        raise VisionAPIError("余额结果格式异常，本次未完成。")
    balances = tuple(
        Balance(
            info["currency"],
            total,
            _items(
                info,
                (("赠送余额", "granted_balance"), ("充值余额", "topped_up_balance")),
            ),
        )
        for info in infos
        if isinstance(info, dict)
        and isinstance(info.get("currency"), str)
        and (total := _amount(info.get("total_balance"))) is not None
    )
    available = payload.get("is_available")
    return BalanceResult(
        name, available if isinstance(available, bool) else None, balances
    )


def _parse_kimi(name: str, payload: object, currency: str) -> BalanceResult:
    data = payload.get("data") if isinstance(payload, dict) else None
    raw = data.get("available_balance") if isinstance(data, dict) else None
    total = _amount(raw)
    if total is None:
        raise VisionAPIError("余额结果格式异常，本次未完成。")
    items = _items(
        data, (("代金券余额", "voucher_balance"), ("现金余额", "cash_balance"))
    )
    # 官方说明：可用余额小于等于 0 时无法调用推理接口。
    return BalanceResult(name, float(total) > 0, (Balance(currency, total, items),))


async def query_balance(
    provider: VisionProviderRecord, *, proxy: ProxyConfig | None = None
) -> BalanceResult:
    host = _host(provider)
    entry = _BALANCE_APIS.get(host)
    if entry is None:
        raise VisionAPIError(
            "该接口没有可用 API Key 查询的余额接口，目前支持 DeepSeek 与 Kimi 官方接口。"
        )
    if not provider.api_key:
        raise VisionAPIError("查询余额需要先填写 API Key。")
    name, path, kind, currency = entry
    # 官方主机固定走 HTTPS，即使接口地址误填为 http:// 也不明文发送密钥。
    payload = await request_json(
        "GET",
        f"https://{host}{path}",
        provider,
        proxy=proxy,
        headers={"Authorization": f"Bearer {provider.api_key}"},
    )
    if kind == "deepseek":
        return _parse_deepseek(name, payload)
    return _parse_kimi(name, payload, currency)
