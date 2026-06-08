"""B 站链接解析插件配置。"""

from pydantic import BaseModel, Field


from shared.config.message_templates import LinkMessageTemplates


class Config(BaseModel):
    bilibili_cookie: str = Field(default="", description="B 站 Cookie（直播解析必需，与全局账号设置共用）")
    message_templates: LinkMessageTemplates = Field(default_factory=LinkMessageTemplates)

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            bilibili_cookie=snap.bilibili_cookie,
            message_templates=snap.link_message_templates,
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
