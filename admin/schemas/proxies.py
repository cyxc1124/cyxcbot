"""Shared outbound proxy schemas."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from admin.schemas.settings import ProxyResponse

ProxyScheme = Literal["http", "https", "socks5"]


class ProxyCreate(BaseModel):
    name: str = Field(max_length=64)
    scheme: ProxyScheme
    host: str = Field(max_length=255)
    # 端口范围由共享校验给出中文提示，这里不做数值约束。
    port: int
    username: str = Field(default="", max_length=128)
    password: Optional[str] = Field(default=None, max_length=256, repr=False)


class ProxyPatch(BaseModel):
    """只更新传入的字段；password 省略时保留已存密码，空字符串表示清除。"""

    name: Optional[str] = Field(default=None, max_length=64)
    scheme: Optional[ProxyScheme] = None
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = None
    username: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, max_length=256, repr=False)


class ProxiesResponse(BaseModel):
    """保存后的完整列表；id 为本次新增或修改的代理。"""

    id: Optional[str] = None
    proxies: list[ProxyResponse] = Field(default_factory=list)


class ProxyTestRequest(BaseModel):
    """未保存的表单值；password 为 None 时沿用已保存代理的密码。"""

    id: Optional[str] = Field(default=None, max_length=32)
    scheme: ProxyScheme
    host: str = Field(max_length=255)
    port: int
    username: str = Field(default="", max_length=128)
    password: Optional[str] = Field(default=None, max_length=256, repr=False)


class ProxyTestTarget(BaseModel):
    name: str
    url: str
    reachable: bool
    message: str
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None


class ProxyTestResponse(BaseModel):
    success: bool
    message: str
    targets: list[ProxyTestTarget] = Field(default_factory=list)
