"""AI image detection vision-provider probe schemas."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from admin.schemas.settings import AiImageVisionProviderResponse


class VisionProviderCreate(BaseModel):
    name: str = Field(max_length=64)
    api_type: Literal["openai", "anthropic"]
    base_url: str = Field(default="", max_length=512)
    model: str = Field(max_length=256)
    enabled: bool = True
    proxy_id: str = Field(default="", max_length=32)
    api_key: Optional[str] = Field(default=None, max_length=1024, repr=False)


class VisionProviderPatch(BaseModel):
    """只更新传入的字段；api_key 省略时保留已存密钥，空字符串表示清除。"""

    name: Optional[str] = Field(default=None, max_length=64)
    api_type: Optional[Literal["openai", "anthropic"]] = None
    base_url: Optional[str] = Field(default=None, max_length=512)
    model: Optional[str] = Field(default=None, max_length=256)
    enabled: Optional[bool] = None
    proxy_id: Optional[str] = Field(default=None, max_length=32)
    api_key: Optional[str] = Field(default=None, max_length=1024, repr=False)


class VisionProvidersResponse(BaseModel):
    """保存后的完整列表；id 为本次新增或修改的供应商。"""

    id: Optional[str] = None
    providers: list[AiImageVisionProviderResponse] = Field(default_factory=list)


class VisionProbeRequest(BaseModel):
    """未保存的表单值；api_key 为 None 时沿用已保存供应商的密钥。"""

    id: Optional[str] = Field(default=None, max_length=32)
    api_type: Literal["openai", "anthropic"]
    base_url: str = Field(default="", max_length=512)
    model: str = Field(default="", max_length=256)
    proxy_id: str = Field(default="", max_length=32)
    api_key: Optional[str] = Field(default=None, max_length=1024, repr=False)


class VisionModelInfo(BaseModel):
    id: str
    name: str = ""
    vision: Optional[bool] = None


class VisionModelsResponse(BaseModel):
    success: bool
    message: str
    models: list[VisionModelInfo] = Field(default_factory=list)


class VisionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None
    verdict: Optional[str] = None
    confidence: Optional[int] = None
    reason: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class VisionBalanceItem(BaseModel):
    label: str
    amount: str


class VisionBalance(BaseModel):
    currency: str
    total: str
    items: list[VisionBalanceItem] = Field(default_factory=list)


class VisionBalanceResponse(BaseModel):
    success: bool
    message: str
    provider: str = ""
    available: Optional[bool] = None
    balances: list[VisionBalance] = Field(default_factory=list)
