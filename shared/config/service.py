"""ConfigService singleton: load config from DB, hot reload, notify monitors."""

from __future__ import annotations

import json
from typing import Awaitable, Callable, List, Optional

from nonebot.log import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from nonebot_plugin_orm import get_session

from shared.config.nonebot_superusers import apply_nonebot_superusers
from shared.config.types import AppConfigSnapshot
from shared.db.models import (
    DynamicTarget,
    LiveTarget,
    SystemSetting,
)
from shared.security.crypto import decrypt_value

ReloadCallback = Callable[[AppConfigSnapshot], Awaitable[None]]

SETTING_KEYS = {
    "dynamic_monitor_interval": ("30", int),
    "dynamic_enable_screenshot": ("true", bool),
    "live_monitor_interval": ("60", int),
    "live_monitor_include_info": ("true", bool),
    "live_monitor_use_websocket": ("true", bool),
    "bilibili_cookie_encrypted": ("", str),
    "audit_log_retention_days": ("90", int),
    "event_retention_days": ("90", int),
    "message_group_restrict": ("false", bool),
    "message_enabled_group_ids": ("[]", "json_list"),
    "status_check_allowed_qq": ("[]", "json_list"),
    "nonebot_superusers": ("[]", "json_list"),
}


def _parse_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


class ConfigService:
    """Singleton service for DB-backed configuration."""

    _instance: Optional["ConfigService"] = None

    def __init__(self) -> None:
        self._snapshot = AppConfigSnapshot()
        self._reload_callbacks: List[ReloadCallback] = []

    @classmethod
    def get_instance(cls) -> "ConfigService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def snapshot(self) -> AppConfigSnapshot:
        return self._snapshot

    def get_snapshot(self) -> AppConfigSnapshot:
        return self._snapshot

    def register_reload_callback(self, callback: ReloadCallback) -> None:
        self._reload_callbacks.append(callback)

    async def load(self) -> AppConfigSnapshot:
        """Load full config snapshot from database."""
        session = get_session()
        async with session.begin():
            settings = await self._load_settings(session)
            dynamic_mapping = await self._load_dynamic_mapping(session)
            live_mapping = await self._load_live_mapping(session)
            dynamic_at_all = await self._load_dynamic_at_all(session)
            live_at_all = await self._load_live_at_all(session)

        cookie_encrypted = settings.get("bilibili_cookie_encrypted", "")
        cookie = ""
        if cookie_encrypted:
            try:
                cookie = decrypt_value(cookie_encrypted)
            except ValueError as exc:
                logger.error(f"Failed to decrypt bilibili cookie: {exc}")

        self._snapshot = AppConfigSnapshot(
            dynamic_monitor_mapping=dynamic_mapping,
            dynamic_at_all=dynamic_at_all,
            dynamic_monitor_interval=settings.get("dynamic_monitor_interval", 30),
            dynamic_enable_screenshot=settings.get("dynamic_enable_screenshot", True),
            live_monitor_mapping=live_mapping,
            live_at_all=live_at_all,
            live_monitor_interval=settings.get("live_monitor_interval", 60),
            live_monitor_include_info=settings.get("live_monitor_include_info", True),
            live_monitor_use_websocket=settings.get("live_monitor_use_websocket", True),
            bilibili_cookie=cookie,
            bilibili_cookie_set=bool(cookie_encrypted),
            audit_log_retention_days=settings.get("audit_log_retention_days", 90),
            event_retention_days=settings.get("event_retention_days", 90),
            message_group_restrict=settings.get("message_group_restrict", False),
            message_enabled_group_ids=settings.get("message_enabled_group_ids", []),
            status_check_allowed_qq=settings.get("status_check_allowed_qq", []),
            nonebot_superusers=settings.get("nonebot_superusers", []),
        )
        apply_nonebot_superusers(self._snapshot.nonebot_superusers)
        logger.info(
            f"Config loaded from DB: {len(dynamic_mapping)} dynamic targets, "
            f"{len(live_mapping)} live targets"
        )
        return self._snapshot

    async def reload(self) -> AppConfigSnapshot:
        """Reload config and notify registered monitors."""
        snapshot = await self.load()
        for callback in self._reload_callbacks:
            try:
                await callback(snapshot)
            except Exception as exc:
                logger.error(f"Config reload callback failed: {exc}")
        return snapshot

    async def get_setting(self, key: str) -> Optional[str]:
        session = get_session()
        async with session.begin():
            row = await session.get(SystemSetting, key)
            return row.value if row else None

    async def set_settings(self, values: dict[str, str]) -> None:
        session = get_session()
        async with session.begin():
            for key, value in values.items():
                row = await session.get(SystemSetting, key)
                if row:
                    row.value = value
                else:
                    session.add(SystemSetting(key=key, value=value))

    async def _load_settings(self, session) -> dict:
        result: dict = {}
        rows = (await session.scalars(select(SystemSetting))).all()
        raw = {row.key: row.value for row in rows}

        for key, (default, typ) in SETTING_KEYS.items():
            value = raw.get(key, default)
            if typ is int:
                try:
                    parsed = int(value)
                except ValueError:
                    parsed = int(default)
                if "retention" in key:
                    result[key] = max(0, min(3650, parsed))
                elif key.startswith("dynamic"):
                    result[key] = max(10, min(3600, parsed))
                else:
                    result[key] = max(30, min(3600, parsed))
            elif typ is bool:
                result[key] = _parse_bool(value)
            elif typ == "json_list":
                try:
                    parsed = json.loads(value or "[]")
                    if isinstance(parsed, list):
                        result[key] = [str(item) for item in parsed if str(item)]
                    else:
                        result[key] = []
                except json.JSONDecodeError:
                    result[key] = []
            else:
                result[key] = value
        return result

    async def _load_dynamic_mapping(self, session) -> dict[str, list[str]]:
        stmt = (
            select(DynamicTarget)
            .where(DynamicTarget.enabled.is_(True))
            .options(selectinload(DynamicTarget.groups))
        )
        targets = (await session.scalars(stmt)).all()
        mapping: dict[str, list[str]] = {}
        for target in targets:
            mapping[target.uid] = [g.group_id for g in target.groups]
        return mapping

    async def _load_dynamic_at_all(self, session) -> dict[str, bool]:
        stmt = select(DynamicTarget).where(DynamicTarget.enabled.is_(True))
        targets = (await session.scalars(stmt)).all()
        return {target.uid: target.at_all for target in targets}

    async def _load_live_mapping(self, session) -> dict[str, list[str]]:
        stmt = (
            select(LiveTarget)
            .where(LiveTarget.enabled.is_(True))
            .options(selectinload(LiveTarget.groups))
        )
        targets = (await session.scalars(stmt)).all()
        mapping: dict[str, list[str]] = {}
        for target in targets:
            mapping[target.room_id] = [g.group_id for g in target.groups]
        return mapping

    async def _load_live_at_all(self, session) -> dict[str, bool]:
        stmt = select(LiveTarget).where(LiveTarget.enabled.is_(True))
        targets = (await session.scalars(stmt)).all()
        return {target.room_id: target.at_all for target in targets}

    def settings_for_api(self) -> dict:
        """Settings dict for API (cookie masked, never plaintext)."""
        from shared.security.crypto import mask_secret

        snap = self._snapshot
        masked = mask_secret(snap.bilibili_cookie) if snap.bilibili_cookie else ""
        return {
            "dynamic_monitor_interval": snap.dynamic_monitor_interval,
            "dynamic_enable_screenshot": snap.dynamic_enable_screenshot,
            "live_monitor_interval": snap.live_monitor_interval,
            "live_monitor_include_info": snap.live_monitor_include_info,
            "live_monitor_use_websocket": snap.live_monitor_use_websocket,
            "bilibili_cookie": {
                "configured": snap.bilibili_cookie_set,
                "preview": masked or None,
            },
            "audit_log_retention_days": snap.audit_log_retention_days,
            "event_retention_days": snap.event_retention_days,
            "status_check_allowed_qq": snap.status_check_allowed_qq,
            "nonebot_superusers": snap.nonebot_superusers,
        }

    @staticmethod
    def serialize_details(data: dict) -> str:
        return json.dumps(data, ensure_ascii=False, default=str)


def get_config_service() -> ConfigService:
    return ConfigService.get_instance()
