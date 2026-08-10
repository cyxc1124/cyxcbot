"""ConfigService singleton: load config from DB, hot reload, notify monitors."""

from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable, List, Optional, TypeAlias

from nonebot.log import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from shared.config.command_aliases import (
    DEFAULT_EXTRA_PREFIXES,
    command_prefixes,
    normalize_command_aliases,
    normalize_extra_prefixes,
    serialize_command_aliases,
)
from shared.config.douyin_link_parser_policy import (
    DouyinLinkParserGroupPolicyRecord,
    DouyinLinkParserUserPolicyRecord,
)
from shared.config.link_parser_policy import (
    LinkParserGroupPolicyRecord,
    LinkParserUserPolicyRecord,
)
from shared.config.message_templates import (
    MESSAGE_TEMPLATE_KEYS,
    douyin_link_templates_from_settings,
    dynamic_templates_from_settings,
    link_templates_from_settings,
    live_templates_from_settings,
    x_link_templates_from_settings,
    x_templates_from_settings,
)
from shared.config.nonebot_superusers import apply_nonebot_superusers
from shared.config.proxy import ProxyConfig
from shared.config.rust_player import MAX_RUST_PLAYER_POINTS
from shared.config.rust_rcon import (
    RustRconBindingRecord,
    warn_rust_rcon_command_alias_conflicts,
)
from shared.config.rust_rcon_custom import RustRconCustomCommandRecord
from shared.config.rust_rcon_policy import (
    RustRconGroupPolicyRecord,
    RustRconUserPolicyRecord,
)
from shared.config.shared_media import (
    default_shared_media_dir,
    resolve_shared_media_dir,
)
from shared.config.types import AppConfigSnapshot
from shared.config.x_link_parser_policy import (
    XLinkParserGroupPolicyRecord,
    XLinkParserUserPolicyRecord,
)
from shared.db.models import (
    DouyinLinkParserGroupPolicy,
    DouyinLinkParserUserPolicy,
    DynamicMonitorState,
    DynamicTarget,
    LinkParserGroupPolicy,
    LinkParserUserPolicy,
    LiveMonitorState,
    LiveTarget,
    RustRconBinding,
    RustRconCustomCommand,
    RustRconGroupPolicy,
    RustRconUserPolicy,
    SystemSetting,
    XLinkParserGroupPolicy,
    XLinkParserUserPolicy,
    XMonitorState,
    XTarget,
)
from shared.security.crypto import decrypt_value

ReloadCallback = Callable[[AppConfigSnapshot], Awaitable[None]]
UnregisterReloadCallback: TypeAlias = Callable[[], None]

SETTING_KEYS = {
    "dynamic_monitor_interval": ("30", int),
    "dynamic_monitor_use_stagger": ("true", bool),
    "dynamic_enable_screenshot": ("true", bool),
    "live_monitor_interval": ("60", int),
    "live_monitor_include_info": ("true", bool),
    "live_monitor_use_websocket": ("true", bool),
    "bilibili_cookie_encrypted": ("", str),
    "douyin_cookie_encrypted": ("", str),
    "message_group_restrict": ("true", bool),
    "message_enabled_group_ids": ("[]", "json_list"),
    "message_private_restrict": ("true", bool),
    "message_enabled_user_ids": ("[]", "json_list"),
    "status_check_group_restrict": ("true", bool),
    "status_check_enabled_group_ids": ("[]", "json_list"),
    "status_check_private_restrict": ("true", bool),
    "status_check_enabled_user_ids": ("[]", "json_list"),
    "status_check_show_detailed": ("true", bool),
    "status_check_show_uptime": ("true", bool),
    "status_check_show_memory": ("true", bool),
    "status_check_allowed_qq": ("[]", "json_list"),
    "group_special_title_restrict": ("true", bool),
    "group_special_title_enabled_group_ids": ("[]", "json_list"),
    "group_special_title_daily_limit": ("10", int),
    "nonebot_superusers": ("[]", "json_list"),
    "command_aliases": ("{}", "json_object"),
    "command_extra_prefixes": (
        json.dumps(list(DEFAULT_EXTRA_PREFIXES), ensure_ascii=False),
        "json_prefix_list",
    ),
    "rust_checkin_points_min": ("1", int),
    "rust_checkin_points_max": ("10", int),
    "rust_checkin_online_bonus_points": ("50", int),
    "rust_steam_bind_bonus_points": ("200", int),
    "rust_checkin_rcon_binding_id": ("0", int),
    # 空字符串 = 运行时默认 data/tmp；与 LLBot 共用时在 Web Admin 设 QQ 路径
    "link_parser_shared_media_dir": ("", str),
    "x_monitor_interval": ("120", int),
    "x_monitor_use_stagger": ("true", bool),
    "x_api_bearer_encrypted": ("", str),
    "x_proxy_enabled": ("false", bool),
    "x_proxy_scheme": ("http", str),
    "x_proxy_host": ("", str),
    "x_proxy_port": ("7890", int),
    "x_proxy_username": ("", str),
    "x_proxy_password_encrypted": ("", str),
}

for key, default in MESSAGE_TEMPLATE_KEYS.items():
    SETTING_KEYS[key] = (default, str)


def _parse_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


class ConfigService:
    """Singleton service for DB-backed configuration."""

    _instance: Optional["ConfigService"] = None

    def __init__(self) -> None:
        self._snapshot = AppConfigSnapshot()
        self._reload_callbacks: List[ReloadCallback] = []
        self._reload_lock = asyncio.Lock()
        self._reload_task: asyncio.Task[AppConfigSnapshot] | None = None
        self._reload_pending = False

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

    def register_reload_callback(
        self, callback: ReloadCallback
    ) -> UnregisterReloadCallback:
        """Register a reload callback. Returns a function to unregister it."""
        if callback not in self._reload_callbacks:
            self._reload_callbacks.append(callback)
        return lambda: self.unregister_reload_callback(callback)

    def unregister_reload_callback(self, callback: ReloadCallback) -> None:
        """Remove a previously registered reload callback."""
        try:
            self._reload_callbacks.remove(callback)
        except ValueError:
            pass

    async def load(self) -> AppConfigSnapshot:
        """Load full config snapshot from database."""
        async with get_session() as session:
            async with session.begin():
                settings = await self._load_settings(session)
                (
                    dynamic_mapping,
                    dynamic_user_mapping,
                    dynamic_subscription_mapping,
                    dynamic_subscription_user_mapping,
                    dynamic_at_all,
                ) = await self._load_dynamic_target_data(session)
                (
                    live_mapping,
                    live_user_mapping,
                    live_at_all,
                ) = await self._load_live_target_data(session)
                (
                    x_mapping,
                    x_user_mapping,
                    x_at_all,
                    x_user_ids,
                    x_display_names,
                ) = await self._load_x_target_data(session)
                link_parser_group_policies = (
                    await self._load_link_parser_group_policies(session)
                )
                link_parser_user_policies = await self._load_link_parser_user_policies(
                    session
                )
                douyin_link_parser_group_policies = (
                    await self._load_douyin_link_parser_group_policies(session)
                )
                douyin_link_parser_user_policies = (
                    await self._load_douyin_link_parser_user_policies(session)
                )
                x_link_parser_group_policies = (
                    await self._load_x_link_parser_group_policies(session)
                )
                x_link_parser_user_policies = (
                    await self._load_x_link_parser_user_policies(session)
                )
                rust_rcon_bindings = await self._load_rust_rcon_bindings(session)
                rust_rcon_custom_commands = await self._load_rust_rcon_custom_commands(
                    session
                )
                rust_rcon_group_policies = await self._load_rust_rcon_group_policies(
                    session
                )
                rust_rcon_user_policies = await self._load_rust_rcon_user_policies(
                    session
                )
                await self._prune_dynamic_monitor_states(session, set(dynamic_mapping))
                await self._prune_live_monitor_states(session, set(live_mapping))
                await self._prune_x_monitor_states(session, set(x_mapping))

        cookie_encrypted = settings.get("bilibili_cookie_encrypted", "")
        cookie = ""
        if cookie_encrypted:
            try:
                cookie = decrypt_value(cookie_encrypted)
            except ValueError as exc:
                logger.error("B 站 Cookie 解密失败: {}", exc)

        douyin_cookie_encrypted = settings.get("douyin_cookie_encrypted", "")
        douyin_cookie = ""
        if douyin_cookie_encrypted:
            try:
                douyin_cookie = decrypt_value(douyin_cookie_encrypted)
            except ValueError as exc:
                logger.error("抖音 Cookie 解密失败: {}", exc)

        x_api_bearer_encrypted = settings.get("x_api_bearer_encrypted", "")
        x_api_bearer = ""
        if x_api_bearer_encrypted:
            try:
                x_api_bearer = decrypt_value(x_api_bearer_encrypted)
            except ValueError as exc:
                logger.error("X API Bearer Token 解密失败: {}", exc)

        x_proxy_password_encrypted = settings.get("x_proxy_password_encrypted", "")
        x_proxy_password = ""
        if x_proxy_password_encrypted:
            try:
                x_proxy_password = decrypt_value(x_proxy_password_encrypted)
            except ValueError as exc:
                logger.error("X 代理密码解密失败: {}", exc)
        settings["x_proxy_password"] = x_proxy_password
        x_proxy = ProxyConfig.from_settings(settings)

        self._snapshot = AppConfigSnapshot(
            dynamic_monitor_mapping=dynamic_mapping,
            dynamic_monitor_user_mapping=dynamic_user_mapping,
            dynamic_subscription_mapping=dynamic_subscription_mapping,
            dynamic_subscription_user_mapping=dynamic_subscription_user_mapping,
            dynamic_at_all=dynamic_at_all,
            dynamic_monitor_interval=settings.get("dynamic_monitor_interval", 30),
            dynamic_monitor_use_stagger=settings.get(
                "dynamic_monitor_use_stagger", True
            ),
            dynamic_enable_screenshot=settings.get("dynamic_enable_screenshot", True),
            dynamic_message_templates=dynamic_templates_from_settings(settings),
            live_monitor_mapping=live_mapping,
            live_monitor_user_mapping=live_user_mapping,
            live_at_all=live_at_all,
            live_monitor_interval=settings.get("live_monitor_interval", 60),
            live_monitor_include_info=settings.get("live_monitor_include_info", True),
            live_monitor_use_websocket=settings.get("live_monitor_use_websocket", True),
            live_message_templates=live_templates_from_settings(settings),
            link_message_templates=link_templates_from_settings(settings),
            douyin_link_message_templates=douyin_link_templates_from_settings(settings),
            x_link_message_templates=x_link_templates_from_settings(settings),
            bilibili_cookie=cookie,
            bilibili_cookie_set=bool(cookie_encrypted),
            douyin_cookie=douyin_cookie,
            douyin_cookie_set=bool(douyin_cookie_encrypted),
            message_group_restrict=settings.get("message_group_restrict", True),
            message_enabled_group_ids=settings.get("message_enabled_group_ids", []),
            message_private_restrict=settings.get("message_private_restrict", True),
            message_enabled_user_ids=settings.get("message_enabled_user_ids", []),
            status_check_group_restrict=settings.get(
                "status_check_group_restrict", True
            ),
            status_check_enabled_group_ids=settings.get(
                "status_check_enabled_group_ids", []
            ),
            status_check_private_restrict=settings.get(
                "status_check_private_restrict", True
            ),
            status_check_enabled_user_ids=settings.get(
                "status_check_enabled_user_ids", []
            ),
            status_check_show_detailed=settings.get("status_check_show_detailed", True),
            status_check_show_uptime=settings.get("status_check_show_uptime", True),
            status_check_show_memory=settings.get("status_check_show_memory", True),
            status_check_allowed_qq=settings.get("status_check_allowed_qq", []),
            group_special_title_restrict=settings.get(
                "group_special_title_restrict", True
            ),
            group_special_title_enabled_group_ids=settings.get(
                "group_special_title_enabled_group_ids", []
            ),
            group_special_title_daily_limit=settings.get(
                "group_special_title_daily_limit", 10
            ),
            nonebot_superusers=settings.get("nonebot_superusers", []),
            link_parser_group_policies=link_parser_group_policies,
            link_parser_user_policies=link_parser_user_policies,
            douyin_link_parser_group_policies=douyin_link_parser_group_policies,
            douyin_link_parser_user_policies=douyin_link_parser_user_policies,
            x_link_parser_group_policies=x_link_parser_group_policies,
            x_link_parser_user_policies=x_link_parser_user_policies,
            command_aliases=settings.get("command_aliases", {}),
            command_extra_prefixes=settings.get(
                "command_extra_prefixes", list(DEFAULT_EXTRA_PREFIXES)
            ),
            rust_rcon_bindings=rust_rcon_bindings,
            rust_rcon_custom_commands=rust_rcon_custom_commands,
            rust_rcon_group_policies=rust_rcon_group_policies,
            rust_rcon_user_policies=rust_rcon_user_policies,
            rust_checkin_points_min=settings.get("rust_checkin_points_min", 1),
            rust_checkin_points_max=settings.get("rust_checkin_points_max", 10),
            rust_checkin_online_bonus_points=settings.get(
                "rust_checkin_online_bonus_points", 50
            ),
            rust_steam_bind_bonus_points=settings.get(
                "rust_steam_bind_bonus_points", 200
            ),
            rust_checkin_rcon_binding_id=settings.get(
                "rust_checkin_rcon_binding_id", 0
            ),
            link_parser_shared_media_dir=settings.get(
                "link_parser_shared_media_dir", ""
            )
            or "",
            x_monitor_mapping=x_mapping,
            x_monitor_user_mapping=x_user_mapping,
            x_at_all=x_at_all,
            x_user_ids=x_user_ids,
            x_display_names=x_display_names,
            x_monitor_interval=settings.get("x_monitor_interval", 120),
            x_monitor_use_stagger=settings.get("x_monitor_use_stagger", True),
            x_message_templates=x_templates_from_settings(settings),
            x_api_bearer=x_api_bearer,
            x_api_bearer_set=bool(x_api_bearer_encrypted),
            x_proxy=x_proxy,
        )
        apply_nonebot_superusers(self._snapshot.nonebot_superusers)
        warn_rust_rcon_command_alias_conflicts(
            self._snapshot.command_aliases, self._snapshot.rust_rcon_bindings
        )
        logger.info(
            "配置已从数据库加载: {} 个动态目标, {} 个直播目标, {} 个 X 目标",
            len(dynamic_mapping),
            len(live_mapping),
            len(x_mapping),
        )
        return self._snapshot

    async def reload(self) -> AppConfigSnapshot:
        """Reload config and notify registered monitors (single-flight)."""
        async with self._reload_lock:
            if self._reload_task is None or self._reload_task.done():
                self._reload_task = asyncio.create_task(self._run_reload_loop())
            else:
                self._reload_pending = True
            task = self._reload_task
        return await asyncio.shield(task)

    async def _run_reload_loop(self) -> AppConfigSnapshot:
        while True:
            snapshot = await self._do_reload()
            async with self._reload_lock:
                if not self._reload_pending:
                    return snapshot
                self._reload_pending = False

    async def _do_reload(self) -> AppConfigSnapshot:
        logger.info("正在从数据库热重载配置…")
        snapshot = await self.load()
        for callback in list(self._reload_callbacks):
            try:
                await callback(snapshot)
            except Exception:
                logger.opt(exception=True).error("配置热重载回调执行失败")
        logger.info("配置热重载完成")
        return snapshot

    async def get_setting(self, key: str) -> Optional[str]:
        async with get_session() as session:
            async with session.begin():
                row = await session.get(SystemSetting, key)
                return row.value if row else None

    async def set_settings(self, values: dict[str, str]) -> None:
        async with get_session() as session:
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
                elif key == "x_proxy_port":
                    result[key] = max(1, min(65535, parsed))
                elif key.startswith("dynamic") or key.startswith("x_"):
                    result[key] = max(10, min(3600, parsed))
                elif key == "group_special_title_daily_limit":
                    result[key] = max(0, min(100, parsed))
                elif (
                    key.startswith("rust_checkin_points")
                    or key.startswith("rust_checkin_online_bonus")
                    or key == "rust_steam_bind_bonus_points"
                ):
                    result[key] = max(0, min(MAX_RUST_PLAYER_POINTS, parsed))
                elif key == "rust_checkin_rcon_binding_id":
                    result[key] = max(0, parsed)
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
            elif typ == "json_object":
                try:
                    parsed = json.loads(value or "{}")
                except json.JSONDecodeError:
                    parsed = {}
                result[key] = normalize_command_aliases(parsed)
            elif typ == "json_prefix_list":
                try:
                    parsed = json.loads(value or "[]")
                except json.JSONDecodeError:
                    parsed = []
                result[key] = normalize_extra_prefixes(parsed)
            elif typ is str and key in MESSAGE_TEMPLATE_KEYS:
                text = (value or default).strip()
                result[key] = text[:500] if text else default
            else:
                result[key] = value

        return result

    async def _prune_dynamic_monitor_states(
        self, session, active_uids: set[str]
    ) -> None:
        """Drop persisted dynamic monitor state for disabled or removed targets."""
        stmt = delete(DynamicMonitorState)
        if active_uids:
            stmt = stmt.where(DynamicMonitorState.uid.not_in(active_uids))
        result = await session.execute(stmt)
        deleted = result.rowcount or 0
        if deleted:
            logger.info(
                "已清除 {} 条动态监控持久化状态（当前启用目标: {} 个）",
                deleted,
                len(active_uids),
            )

    async def _prune_live_monitor_states(
        self, session, active_room_ids: set[str]
    ) -> None:
        """Drop persisted live monitor state for disabled or removed targets."""
        stmt = delete(LiveMonitorState)
        if active_room_ids:
            stmt = stmt.where(LiveMonitorState.room_id.not_in(active_room_ids))
        result = await session.execute(stmt)
        deleted = result.rowcount or 0
        if deleted:
            logger.info(
                "已清除 {} 条直播监控持久化状态（当前启用目标: {} 个）",
                deleted,
                len(active_room_ids),
            )

    async def _prune_x_monitor_states(
        self, session, active_usernames: set[str]
    ) -> None:
        """Drop persisted X monitor state for disabled or removed targets."""
        stmt = delete(XMonitorState)
        if active_usernames:
            stmt = stmt.where(XMonitorState.username.not_in(active_usernames))
        result = await session.execute(stmt)
        deleted = result.rowcount or 0
        if deleted:
            logger.info(
                "已清除 {} 条 X 监控持久化状态（当前启用目标: {} 个）",
                deleted,
                len(active_usernames),
            )

    async def _load_dynamic_target_data(
        self, session
    ) -> tuple[
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, bool],
    ]:
        """One query for all dynamic targets; derive monitor/subscription mappings."""
        stmt = select(DynamicTarget).options(
            selectinload(DynamicTarget.groups),
            selectinload(DynamicTarget.users),
        )
        targets = (await session.scalars(stmt)).all()
        mapping: dict[str, list[str]] = {}
        user_mapping: dict[str, list[str]] = {}
        subscription_mapping: dict[str, list[str]] = {}
        subscription_user_mapping: dict[str, list[str]] = {}
        at_all: dict[str, bool] = {}
        for target in targets:
            if target.groups:
                subscription_mapping[target.uid] = [g.group_id for g in target.groups]
            if target.users:
                subscription_user_mapping[target.uid] = [
                    u.user_id for u in target.users
                ]
            if not target.enabled:
                continue
            mapping[target.uid] = [g.group_id for g in target.groups]
            user_mapping[target.uid] = [u.user_id for u in target.users]
            at_all[target.uid] = target.at_all
        return (
            mapping,
            user_mapping,
            subscription_mapping,
            subscription_user_mapping,
            at_all,
        )

    async def _load_live_target_data(
        self, session
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, bool]]:
        """One query for enabled live targets; derive monitor mappings."""
        stmt = (
            select(LiveTarget)
            .where(LiveTarget.enabled.is_(True))
            .options(
                selectinload(LiveTarget.groups),
                selectinload(LiveTarget.users),
            )
        )
        targets = (await session.scalars(stmt)).all()
        mapping: dict[str, list[str]] = {}
        user_mapping: dict[str, list[str]] = {}
        at_all: dict[str, bool] = {}
        for target in targets:
            mapping[target.room_id] = [g.group_id for g in target.groups]
            user_mapping[target.room_id] = [u.user_id for u in target.users]
            at_all[target.room_id] = target.at_all
        return mapping, user_mapping, at_all

    async def _load_x_target_data(
        self, session
    ) -> tuple[
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, bool],
        dict[str, str],
        dict[str, str],
    ]:
        """One query for enabled X targets; derive monitor mappings and profile cache."""
        stmt = (
            select(XTarget)
            .where(XTarget.enabled.is_(True))
            .options(
                selectinload(XTarget.groups),
                selectinload(XTarget.users),
            )
        )
        targets = (await session.scalars(stmt)).all()
        mapping: dict[str, list[str]] = {}
        user_mapping: dict[str, list[str]] = {}
        at_all: dict[str, bool] = {}
        x_user_ids: dict[str, str] = {}
        x_display_names: dict[str, str] = {}
        for target in targets:
            username = (target.username or "").strip().lstrip("@").strip().lower()
            if not username:
                continue
            mapping[username] = [g.group_id for g in target.groups]
            user_mapping[username] = [u.user_id for u in target.users]
            at_all[username] = target.at_all
            if target.user_id:
                x_user_ids[username] = str(target.user_id).strip()
            if target.name and target.name.strip():
                x_display_names[username] = target.name.strip()
        return mapping, user_mapping, at_all, x_user_ids, x_display_names

    async def _load_link_parser_group_policies(
        self, session
    ) -> dict[str, LinkParserGroupPolicyRecord]:
        rows = (await session.scalars(select(LinkParserGroupPolicy))).all()
        return {
            row.group_id: LinkParserGroupPolicyRecord(
                group_id=row.group_id,
                video_enabled=row.video_enabled,
                live_enabled=row.live_enabled,
                dynamic_enabled=row.dynamic_enabled,
                send_video_enabled=row.send_video_enabled,
            )
            for row in rows
        }

    async def _load_link_parser_user_policies(
        self, session
    ) -> dict[str, LinkParserUserPolicyRecord]:
        rows = (await session.scalars(select(LinkParserUserPolicy))).all()
        return {
            row.user_id: LinkParserUserPolicyRecord(
                user_id=row.user_id,
                video_enabled=row.video_enabled,
                live_enabled=row.live_enabled,
                dynamic_enabled=row.dynamic_enabled,
                send_video_enabled=row.send_video_enabled,
                name=row.name,
            )
            for row in rows
        }

    async def _load_douyin_link_parser_group_policies(
        self, session
    ) -> dict[str, DouyinLinkParserGroupPolicyRecord]:
        rows = (await session.scalars(select(DouyinLinkParserGroupPolicy))).all()
        return {
            row.group_id: DouyinLinkParserGroupPolicyRecord(
                group_id=row.group_id,
                enabled=row.enabled,
            )
            for row in rows
        }

    async def _load_douyin_link_parser_user_policies(
        self, session
    ) -> dict[str, DouyinLinkParserUserPolicyRecord]:
        rows = (await session.scalars(select(DouyinLinkParserUserPolicy))).all()
        return {
            row.user_id: DouyinLinkParserUserPolicyRecord(
                user_id=row.user_id,
                enabled=row.enabled,
                name=row.name,
            )
            for row in rows
        }

    async def _load_x_link_parser_group_policies(
        self, session
    ) -> dict[str, XLinkParserGroupPolicyRecord]:
        rows = (await session.scalars(select(XLinkParserGroupPolicy))).all()
        return {
            row.group_id: XLinkParserGroupPolicyRecord(
                group_id=row.group_id,
                enabled=row.enabled,
            )
            for row in rows
        }

    async def _load_x_link_parser_user_policies(
        self, session
    ) -> dict[str, XLinkParserUserPolicyRecord]:
        rows = (await session.scalars(select(XLinkParserUserPolicy))).all()
        return {
            row.user_id: XLinkParserUserPolicyRecord(
                user_id=row.user_id,
                enabled=row.enabled,
                name=row.name,
            )
            for row in rows
        }

    async def _load_rust_rcon_bindings(self, session) -> list[RustRconBindingRecord]:
        stmt = (
            select(RustRconBinding)
            .options(selectinload(RustRconBinding.allowed_users))
            .order_by(RustRconBinding.id)
        )
        rows = (await session.scalars(stmt)).all()
        bindings: list[RustRconBindingRecord] = []
        for row in rows:
            password = ""
            if row.password_encrypted:
                try:
                    password = decrypt_value(row.password_encrypted)
                except ValueError as exc:
                    logger.error("Rust RCON 绑定 {} 密码解密失败: {}", row.alias, exc)
            allowed_qq_ids = tuple(
                sorted(
                    {str(item.user_id) for item in row.allowed_users},
                    key=lambda value: (not value.isdigit(), value),
                )
            )
            bindings.append(
                RustRconBindingRecord(
                    id=row.id,
                    alias=row.alias,
                    host=row.host,
                    port=row.port,
                    password=password,
                    enabled=row.enabled,
                    name=row.name,
                    allowed_qq_ids=allowed_qq_ids,
                )
            )
        return bindings

    async def _load_rust_rcon_custom_commands(
        self, session
    ) -> list[RustRconCustomCommandRecord]:
        stmt = (
            select(RustRconCustomCommand)
            .options(selectinload(RustRconCustomCommand.allowed_users))
            .order_by(RustRconCustomCommand.id)
        )
        rows = (await session.scalars(stmt)).all()
        return [
            RustRconCustomCommandRecord(
                id=row.id,
                name=row.name,
                template=row.template,
                binding_id=row.binding_id,
                enabled=row.enabled,
                allowed_qq_ids=tuple(
                    sorted(
                        {str(item.user_id) for item in row.allowed_users},
                        key=lambda value: (not value.isdigit(), value),
                    )
                ),
            )
            for row in rows
        ]

    async def _load_rust_rcon_group_policies(
        self, session
    ) -> dict[str, RustRconGroupPolicyRecord]:
        rows = (await session.scalars(select(RustRconGroupPolicy))).all()
        return {
            row.group_id: RustRconGroupPolicyRecord(
                group_id=row.group_id,
                enabled=row.enabled,
            )
            for row in rows
        }

    async def _load_rust_rcon_user_policies(
        self, session
    ) -> dict[str, RustRconUserPolicyRecord]:
        rows = (await session.scalars(select(RustRconUserPolicy))).all()
        return {
            row.user_id: RustRconUserPolicyRecord(
                user_id=row.user_id,
                enabled=row.enabled,
                name=row.name,
            )
            for row in rows
        }

    async def upsert_rust_rcon_group_policy(
        self, group_id: str, *, enabled: bool
    ) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(RustRconGroupPolicy, gid)
                if row:
                    row.enabled = enabled
                else:
                    session.add(RustRconGroupPolicy(group_id=gid, enabled=enabled))

    async def delete_rust_rcon_group_policy(self, group_id: str) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(RustRconGroupPolicy, gid)
                if row:
                    await session.delete(row)

    async def upsert_rust_rcon_user_policy(
        self,
        user_id: str,
        *,
        enabled: bool,
        name: str | None = None,
    ) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(RustRconUserPolicy, uid)
                if row:
                    row.enabled = enabled
                    row.name = name
                else:
                    session.add(
                        RustRconUserPolicy(user_id=uid, enabled=enabled, name=name)
                    )

    async def delete_rust_rcon_user_policy(self, user_id: str) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(RustRconUserPolicy, uid)
                if row:
                    await session.delete(row)

    async def upsert_link_parser_group_policy(
        self,
        group_id: str,
        *,
        video_enabled: bool,
        live_enabled: bool,
        dynamic_enabled: bool,
        send_video_enabled: bool,
    ) -> None:
        from shared.config.link_parser_policy import normalize_link_parser_flags

        video, live, dynamic, send = normalize_link_parser_flags(
            video_enabled=video_enabled,
            live_enabled=live_enabled,
            dynamic_enabled=dynamic_enabled,
            send_video_enabled=send_video_enabled,
        )
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(LinkParserGroupPolicy, gid)
                if row:
                    row.video_enabled = video
                    row.live_enabled = live
                    row.dynamic_enabled = dynamic
                    row.send_video_enabled = send
                else:
                    session.add(
                        LinkParserGroupPolicy(
                            group_id=gid,
                            video_enabled=video,
                            live_enabled=live,
                            dynamic_enabled=dynamic,
                            send_video_enabled=send,
                        )
                    )

    async def delete_link_parser_group_policy(self, group_id: str) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(LinkParserGroupPolicy, gid)
                if row:
                    await session.delete(row)

    async def upsert_link_parser_user_policy(
        self,
        user_id: str,
        *,
        video_enabled: bool,
        live_enabled: bool,
        dynamic_enabled: bool,
        send_video_enabled: bool,
        name: str | None = None,
    ) -> None:
        from shared.config.link_parser_policy import normalize_link_parser_flags

        video, live, dynamic, send = normalize_link_parser_flags(
            video_enabled=video_enabled,
            live_enabled=live_enabled,
            dynamic_enabled=dynamic_enabled,
            send_video_enabled=send_video_enabled,
        )
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(LinkParserUserPolicy, uid)
                if row:
                    row.video_enabled = video
                    row.live_enabled = live
                    row.dynamic_enabled = dynamic
                    row.send_video_enabled = send
                    row.name = name
                else:
                    session.add(
                        LinkParserUserPolicy(
                            user_id=uid,
                            name=name,
                            video_enabled=video,
                            live_enabled=live,
                            dynamic_enabled=dynamic,
                            send_video_enabled=send,
                        )
                    )

    async def delete_link_parser_user_policy(self, user_id: str) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(LinkParserUserPolicy, uid)
                if row:
                    await session.delete(row)

    async def upsert_douyin_link_parser_group_policy(
        self,
        group_id: str,
        *,
        enabled: bool,
    ) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DouyinLinkParserGroupPolicy, gid)
                if row:
                    row.enabled = enabled
                else:
                    session.add(
                        DouyinLinkParserGroupPolicy(group_id=gid, enabled=enabled)
                    )

    async def delete_douyin_link_parser_group_policy(self, group_id: str) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DouyinLinkParserGroupPolicy, gid)
                if row:
                    await session.delete(row)

    async def upsert_douyin_link_parser_user_policy(
        self,
        user_id: str,
        *,
        enabled: bool,
        name: str | None = None,
    ) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DouyinLinkParserUserPolicy, uid)
                if row:
                    row.enabled = enabled
                    row.name = name
                else:
                    session.add(
                        DouyinLinkParserUserPolicy(
                            user_id=uid,
                            name=name,
                            enabled=enabled,
                        )
                    )

    async def delete_douyin_link_parser_user_policy(self, user_id: str) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(DouyinLinkParserUserPolicy, uid)
                if row:
                    await session.delete(row)

    async def upsert_x_link_parser_group_policy(
        self,
        group_id: str,
        *,
        enabled: bool,
    ) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XLinkParserGroupPolicy, gid)
                if row:
                    row.enabled = enabled
                else:
                    session.add(XLinkParserGroupPolicy(group_id=gid, enabled=enabled))

    async def delete_x_link_parser_group_policy(self, group_id: str) -> None:
        gid = str(group_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XLinkParserGroupPolicy, gid)
                if row:
                    await session.delete(row)

    async def upsert_x_link_parser_user_policy(
        self,
        user_id: str,
        *,
        enabled: bool,
        name: str | None = None,
    ) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XLinkParserUserPolicy, uid)
                if row:
                    row.enabled = enabled
                    row.name = name
                else:
                    session.add(
                        XLinkParserUserPolicy(
                            user_id=uid,
                            name=name,
                            enabled=enabled,
                        )
                    )

    async def delete_x_link_parser_user_policy(self, user_id: str) -> None:
        uid = str(user_id).strip()
        async with get_session() as session:
            async with session.begin():
                row = await session.get(XLinkParserUserPolicy, uid)
                if row:
                    await session.delete(row)

    def settings_for_api(self) -> dict:
        """Settings dict for API (cookie masked, never plaintext)."""
        from shared.security.crypto import mask_secret

        snap = self._snapshot
        masked = mask_secret(snap.bilibili_cookie) if snap.bilibili_cookie else ""
        douyin_masked = mask_secret(snap.douyin_cookie) if snap.douyin_cookie else ""
        x_bearer_masked = mask_secret(snap.x_api_bearer) if snap.x_api_bearer else ""
        dt = snap.dynamic_message_templates
        lt = snap.live_message_templates
        link = snap.link_message_templates
        douyin_link = snap.douyin_link_message_templates
        x_link = snap.x_link_message_templates
        xt = snap.x_message_templates
        xp = snap.x_proxy
        return {
            "dynamic_monitor_interval": snap.dynamic_monitor_interval,
            "dynamic_monitor_use_stagger": snap.dynamic_monitor_use_stagger,
            "dynamic_enable_screenshot": snap.dynamic_enable_screenshot,
            "dynamic_template_push": dt.push,
            "dynamic_template_pinned": dt.pinned,
            "dynamic_template_query_latest": dt.query_latest,
            "dynamic_template_query_pinned": dt.query_pinned,
            "dynamic_template_extract": dt.extract,
            "dynamic_template_extract_empty": dt.extract_empty,
            "dynamic_template_extract_failed": dt.extract_failed,
            "dynamic_template_extract_image_label": dt.extract_image_label,
            "live_monitor_interval": snap.live_monitor_interval,
            "live_monitor_include_info": snap.live_monitor_include_info,
            "live_monitor_use_websocket": snap.live_monitor_use_websocket,
            "live_template_start": lt.start,
            "live_template_end": lt.end,
            "link_template_video": link.video,
            "link_template_live": link.live,
            "link_template_douyin": douyin_link.video,
            "link_template_x": x_link.tweet,
            "bilibili_cookie": {
                "configured": snap.bilibili_cookie_set,
                "preview": masked or None,
            },
            "douyin_cookie": {
                "configured": snap.douyin_cookie_set,
                "preview": douyin_masked or None,
            },
            "status_check_allowed_qq": snap.status_check_allowed_qq,
            "nonebot_superusers": snap.nonebot_superusers,
            "command_aliases": serialize_command_aliases(snap.command_aliases)
            if snap.command_aliases
            else serialize_command_aliases(normalize_command_aliases({})),
            "command_extra_prefixes": list(snap.command_extra_prefixes),
            "command_prefixes": sorted(command_prefixes()),
            "link_parser_shared_media_dir": snap.link_parser_shared_media_dir,
            "link_parser_shared_media_dir_default": str(default_shared_media_dir()),
            "link_parser_shared_media_dir_resolved": str(
                resolve_shared_media_dir(snap.link_parser_shared_media_dir)
            ),
            "x_monitor_interval": snap.x_monitor_interval,
            "x_monitor_use_stagger": snap.x_monitor_use_stagger,
            "x_template_push": xt.push,
            "x_api_bearer": {
                "configured": snap.x_api_bearer_set,
                "preview": x_bearer_masked or None,
            },
            "x_proxy": {
                "enabled": xp.enabled,
                "scheme": xp.scheme,
                "host": xp.host,
                "port": xp.port,
                "username": xp.username,
                "password_configured": bool(xp.password),
            },
        }


def get_config_service() -> ConfigService:
    return ConfigService.get_instance()
