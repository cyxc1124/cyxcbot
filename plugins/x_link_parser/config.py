"""X 链接解析插件配置。"""

from pydantic import BaseModel, Field

from shared.config.message_templates import XLinkMessageTemplates
from shared.config.proxy import ProxyConfig


class Config(BaseModel):
    x_api_bearer: str = Field(default="", description="X API Bearer Token")
    x_proxy: ProxyConfig = Field(
        default_factory=ProxyConfig, description="X API 出站代理"
    )
    message_templates: XLinkMessageTemplates = Field(
        default_factory=XLinkMessageTemplates
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            x_api_bearer=snap.x_api_bearer,
            x_proxy=snap.x_proxy,
            message_templates=snap.x_link_message_templates,
        )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_service()
    return _config


def reload_config() -> Config:
    global _config
    _config = Config.from_service()
    return _config
