"""Check that a proxy reaches the overseas APIs used by X and AI image detection."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

from shared.config.proxy import ProxyConfig

# 任何 HTTP 响应（包括未带密钥的 401）都说明经代理能到达该服务。
TARGETS = (
    ("X API", "https://api.x.com/2/openapi.json"),
    ("OpenAI API", "https://api.openai.com/v1/models"),
    ("Anthropic API", "https://api.anthropic.com/v1/models"),
)
TIMEOUT = 10


@dataclass(frozen=True)
class ProxyCheck:
    name: str
    url: str
    reachable: bool
    message: str
    status_code: int | None = None
    latency_ms: int | None = None


async def _check(proxy_url: str | None, name: str, url: str) -> ProxyCheck:
    started = time.perf_counter()
    try:
        async with asyncio.timeout(TIMEOUT):
            # trust_env=False：只测这个代理，不让运行环境的代理变量干扰结果。
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=TIMEOUT,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.get(url)
    except httpx.ProxyError:
        return ProxyCheck(name, url, False, "代理拒绝了连接，请检查协议、用户名和密码")
    except TimeoutError, httpx.TimeoutException:
        return ProxyCheck(name, url, False, "连接超时")
    except httpx.ConnectError:
        return ProxyCheck(name, url, False, "无法连接到代理，或代理无法访问该服务")
    except httpx.HTTPError, httpx.InvalidURL:
        return ProxyCheck(name, url, False, "请求失败")
    return ProxyCheck(
        name,
        url,
        True,
        f"可访问（HTTP {response.status_code}）",
        response.status_code,
        round((time.perf_counter() - started) * 1000),
    )


async def check_proxy(proxy: ProxyConfig) -> list[ProxyCheck]:
    proxy_url = proxy.to_url()
    return list(
        await asyncio.gather(*(_check(proxy_url, name, url) for name, url in TARGETS))
    )
