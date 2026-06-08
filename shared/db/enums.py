"""Shared enums for audit and system events."""

from enum import StrEnum


class AuditAction(StrEnum):
    """Audit log action types."""

    SETUP = "setup"
    LOGIN = "login"
    LOGOUT = "logout"
    SETTINGS_UPDATE = "settings_update"
    DYNAMIC_TARGET_CREATE = "dynamic_target_create"
    DYNAMIC_TARGET_UPDATE = "dynamic_target_update"
    DYNAMIC_TARGET_DELETE = "dynamic_target_delete"
    LIVE_TARGET_CREATE = "live_target_create"
    LIVE_TARGET_UPDATE = "live_target_update"
    LIVE_TARGET_DELETE = "live_target_delete"
    MONITOR_MANUAL_CHECK = "monitor_manual_check"
    MONITOR_RELOAD = "monitor_reload"
    DYNAMIC_PUSH = "dynamic_push"
    LIVE_PUSH = "live_push"


class SystemEventType(StrEnum):
    """System event types for important operational events."""

    BOT_START = "bot_start"
    BOT_STOP = "bot_stop"
    WEB_ADMIN_START = "web_admin_start"
    CONFIG_RELOAD = "config_reload"
    MONITOR_START = "monitor_start"
    MONITOR_STOP = "monitor_stop"
    MONITOR_ERROR = "monitor_error"
    SETUP_COMPLETE = "setup_complete"
