"""Register NoneBot startup hooks for Web Admin and shared services."""

from __future__ import annotations

import asyncio
import os

from nonebot import get_driver
from nonebot.log import logger

driver = get_driver()


@driver.on_startup
async def init_shared_services():
    """Load config from DB."""
    from shared.config.service import get_config_service

    try:
        await get_config_service().load()
        logger.info("共享服务初始化完成")
    except Exception as exc:
        logger.warning("共享服务初始化失败: {}", exc)


@driver.on_startup
async def start_system_metrics_sampler():
    from shared.monitor.system_metrics import start_system_metrics_sampler

    start_system_metrics_sampler()
    logger.debug("系统指标后台采样已启动")


@driver.on_shutdown
async def stop_system_metrics_sampler():
    from shared.monitor.system_metrics import stop_system_metrics_sampler

    await stop_system_metrics_sampler()


@driver.on_startup
async def start_web_admin_server():
    """Launch FastAPI on WEB_PORT alongside NoneBot."""
    if os.getenv("WEB_ADMIN_ENABLED", "true").lower() in ("0", "false", "no"):
        logger.info("已通过 WEB_ADMIN_ENABLED 禁用 Web Admin")
        return

    try:
        import uvicorn

        from admin.app import create_app
        from admin.config import get_web_host, get_web_port
        from shared.logging.broadcast import bridge_uvicorn_loggers
        from shared.security.web_secret import require_web_secret_key

        # Fail closed before binding the port when JWT/Fernet secret is missing
        # or a known insecure placeholder (e.g. compose/env.example defaults).
        require_web_secret_key()

        app = create_app()
        host = get_web_host()
        port = get_web_port()

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            log_config=None,
            access_log=False,
            loop="asyncio",
        )
        bridge_uvicorn_loggers()
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())

        logger.info("Web Admin API 已启动: http://{}:{}", host, port)
    except ValueError as exc:
        logger.warning("Web Admin 未启动: {}", exc)
    except Exception as exc:
        logger.error("Web Admin 启动失败: {}", exc)
