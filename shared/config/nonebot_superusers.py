"""Sync NoneBot superusers from DB-backed config."""

from __future__ import annotations

from nonebot.log import logger


def apply_nonebot_superusers(qq_ids: list[str]) -> None:
    """将 Web Admin 配置的 QQ 号写入 NoneBot driver.config.superusers。"""
    try:
        import nonebot

        driver = nonebot.get_driver()
        superusers = {str(q).strip() for q in qq_ids if str(q).strip().isdigit()}
        driver.config.superusers = superusers
        if superusers:
            logger.info(f"NoneBot 超级用户已更新: {len(superusers)} 个")
        else:
            logger.info("NoneBot 超级用户已清空")
    except RuntimeError:
        logger.debug("NoneBot driver 尚未初始化，跳过超级用户同步")
    except Exception as exc:
        logger.warning(f"同步 NoneBot 超级用户失败: {exc}")
