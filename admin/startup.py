"""Register NoneBot startup hooks for Web Admin and shared services."""

from __future__ import annotations

import asyncio
import os

from nonebot import get_driver
from nonebot.log import logger

driver = get_driver()


@driver.on_startup
async def init_shared_services():
    """Load config from DB and register shared jobs."""
    from shared.audit.cleanup import register_cleanup_job
    from shared.audit.service import write_system_event
    from shared.config.service import get_config_service
    from shared.db.enums import SystemEventType

    try:
        await get_config_service().load()
        register_cleanup_job()
        await write_system_event(SystemEventType.BOT_START, "Bot started, config loaded from DB")
        logger.info("Shared services initialized")
    except Exception as exc:
        logger.warning(f"Shared services init failed: {exc}")


@driver.on_startup
async def start_web_admin_server():
    """Launch FastAPI on WEB_PORT alongside NoneBot."""
    if os.getenv("WEB_ADMIN_ENABLED", "true").lower() in ("0", "false", "no"):
        logger.info("Web Admin disabled via WEB_ADMIN_ENABLED")
        return

    try:
        import uvicorn
        from admin.app import create_app
        from admin.config import get_web_host, get_web_port
        from shared.audit.service import write_system_event
        from shared.db.enums import SystemEventType

        app = create_app()
        host = get_web_host()
        port = get_web_port()

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())

        logger.info(f"Web Admin API started on http://{host}:{port}")
        try:
            await write_system_event(
                SystemEventType.WEB_ADMIN_START,
                f"Web Admin listening on {host}:{port}",
            )
        except Exception:
            pass
    except ValueError as exc:
        logger.warning(f"Web Admin not started: {exc}")
    except Exception as exc:
        logger.error(f"Failed to start Web Admin: {exc}")
