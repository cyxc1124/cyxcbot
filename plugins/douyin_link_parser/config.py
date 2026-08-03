"""抖音链接解析插件配置。"""

from pydantic import BaseModel, Field

from shared.config.message_templates import DouyinLinkMessageTemplates


class Config(BaseModel):
    douyin_cookie: str = Field(default="", description="抖音 Cookie")
    message_templates: DouyinLinkMessageTemplates = Field(
        default_factory=DouyinLinkMessageTemplates
    )

    @classmethod
    def from_service(cls) -> "Config":
        from shared.config.service import get_config_service

        snap = get_config_service().get_snapshot()
        return cls(
            douyin_cookie=snap.douyin_cookie,
            message_templates=snap.douyin_link_message_templates,
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
