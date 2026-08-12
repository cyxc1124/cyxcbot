"""Shared database models for cyxcbot Web Admin."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Model
from .defaults import utcnow


class User(Model):
    """Local admin user."""

    __tablename__ = "shared_db_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


SETUP_COMPLETED_KEY = "__setup_completed__"


class SystemSetting(Model):
    """Key-value system settings stored in DB."""

    __tablename__ = "shared_db_systemsetting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DynamicTarget(Model):
    """UP主 dynamic monitor target."""

    __tablename__ = "shared_db_dynamictarget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    at_all: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    groups: Mapped[list["DynamicTargetGroup"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )
    users: Mapped[list["DynamicTargetUser"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class DynamicTargetGroup(Model):
    """Group mapping for a dynamic target."""

    __tablename__ = "shared_db_dynamictargetgroup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dynamic_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_dynamictarget.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["DynamicTarget"] = relationship(back_populates="groups")

    __table_args__ = (
        UniqueConstraint(
            "dynamic_target_id", "group_id", name="uq_dynamic_target_group"
        ),
    )


class DynamicTargetUser(Model):
    """Friend mapping for a dynamic target."""

    __tablename__ = "shared_db_dynamictargetuser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dynamic_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_dynamictarget.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["DynamicTarget"] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("dynamic_target_id", "user_id", name="uq_dynamic_target_user"),
    )


class LiveTarget(Model):
    """Bilibili live room monitor target."""

    __tablename__ = "shared_db_livetarget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    at_all: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    groups: Mapped[list["LiveTargetGroup"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )
    users: Mapped[list["LiveTargetUser"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class LiveTargetGroup(Model):
    """Group mapping for a live target."""

    __tablename__ = "shared_db_livetargetgroup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_livetarget.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["LiveTarget"] = relationship(back_populates="groups")

    __table_args__ = (
        UniqueConstraint("live_target_id", "group_id", name="uq_live_target_group"),
    )


class LiveTargetUser(Model):
    """Friend mapping for a live target."""

    __tablename__ = "shared_db_livetargetuser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_livetarget.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["LiveTarget"] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("live_target_id", "user_id", name="uq_live_target_user"),
    )


class DynamicMonitorState(Model):
    """Persisted runtime state for dynamic monitor per UID."""

    __tablename__ = "shared_db_dynamicmonitorstate"

    uid: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_dynamic_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pinned_dynamic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LiveMonitorState(Model):
    """Persisted runtime state for live monitor per room."""

    __tablename__ = "shared_db_livemonitorstate"

    room_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    start_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    streamer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class XTarget(Model):
    """X (Twitter) monitor target."""

    __tablename__ = "shared_db_xtarget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    at_all: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    groups: Mapped[list["XTargetGroup"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )
    users: Mapped[list["XTargetUser"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class XTargetGroup(Model):
    """Group mapping for an X target."""

    __tablename__ = "shared_db_xtargetgroup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    x_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_xtarget.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["XTarget"] = relationship(back_populates="groups")

    __table_args__ = (
        UniqueConstraint("x_target_id", "group_id", name="uq_x_target_group"),
    )


class XTargetUser(Model):
    """Friend mapping for an X target."""

    __tablename__ = "shared_db_xtargetuser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    x_target_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_xtarget.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    target: Mapped["XTarget"] = relationship(back_populates="users")

    __table_args__ = (
        UniqueConstraint("x_target_id", "user_id", name="uq_x_target_user"),
    )


class XMonitorState(Model):
    """Persisted runtime state for X monitor per username."""

    __tablename__ = "shared_db_xmonitorstate"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_tweet_id: Mapped[str] = mapped_column(String(32), default="0", nullable=False)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 部分投递失败时保留待重试目标（tweet_id#fingerprint），重启后避免对已成功目标重复推送
    pending_tweet_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pending_group_ids: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pending_user_ids: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LinkParserGroupPolicy(Model):
    """Per-group override for Bilibili link parser."""

    __tablename__ = "shared_db_linkparsergrouppolicy"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dynamic_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    send_video_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LinkParserUserPolicy(Model):
    """Per-user override for Bilibili link parser."""

    __tablename__ = "shared_db_linkparseruserpolicy"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    video_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dynamic_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    send_video_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DouyinLinkParserGroupPolicy(Model):
    """Per-group override for Douyin link parser."""

    __tablename__ = "shared_db_douyinlinkparsergrouppolicy"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DouyinLinkParserUserPolicy(Model):
    """Per-user override for Douyin link parser."""

    __tablename__ = "shared_db_douyinlinkparseruserpolicy"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class XLinkParserGroupPolicy(Model):
    """Per-group override for X link parser."""

    __tablename__ = "shared_db_xlinkparsergrouppolicy"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class XLinkParserUserPolicy(Model):
    """Per-user override for X link parser."""

    __tablename__ = "shared_db_xlinkparseruserpolicy"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustRconBinding(Model):
    """Rust game server RCON endpoint bound to a chat trigger alias."""

    __tablename__ = "shared_db_rustrconbinding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=28016)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    allowed_users: Mapped[list["RustRconBindingAllowedUser"]] = relationship(
        back_populates="binding", cascade="all, delete-orphan"
    )
    custom_commands: Mapped[list["RustRconCustomCommand"]] = relationship(
        back_populates="binding", cascade="all, delete-orphan"
    )


class RustRconBindingAllowedUser(Model):
    """QQ users allowed to trigger a Rust RCON binding."""

    __tablename__ = "shared_db_rustrconbindingalloweduser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    binding_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_rustrconbinding.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    binding: Mapped["RustRconBinding"] = relationship(back_populates="allowed_users")

    __table_args__ = (
        UniqueConstraint("binding_id", "user_id", name="uq_rust_rcon_binding_user"),
    )


class RustRconCustomCommand(Model):
    """Admin-defined chat shortcut that expands to an RCON command template."""

    __tablename__ = "shared_db_rustrconcustomcommand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    template: Mapped[str] = mapped_column(String(512), nullable=False)
    binding_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_rustrconbinding.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    binding: Mapped["RustRconBinding"] = relationship(back_populates="custom_commands")
    allowed_users: Mapped[list["RustRconCustomCommandAllowedUser"]] = relationship(
        back_populates="command", cascade="all, delete-orphan"
    )


class RustRconCustomCommandAllowedUser(Model):
    """QQ users allowed to trigger a Rust RCON custom command."""

    __tablename__ = "shared_db_rustrconcustomcommandalloweduser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_id: Mapped[int] = mapped_column(
        ForeignKey("shared_db_rustrconcustomcommand.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    command: Mapped["RustRconCustomCommand"] = relationship(
        back_populates="allowed_users"
    )

    __table_args__ = (
        UniqueConstraint(
            "command_id", "user_id", name="uq_rust_rcon_custom_command_user"
        ),
    )


class RustRconGroupPolicy(Model):
    """Per-group override for Rust RCON commands."""

    __tablename__ = "shared_db_rustrcongrouppolicy"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustRconUserPolicy(Model):
    """Per-user override for Rust RCON commands."""

    __tablename__ = "shared_db_rustrconuserpolicy"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustSteamBinding(Model):
    """QQ user to SteamID64 binding for Rust community features."""

    __tablename__ = "shared_db_ruststeambinding"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    steam_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustPlayerPoints(Model):
    """Per-group points balance for a QQ user."""

    __tablename__ = "shared_db_rustplayerpoints"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustShopItem(Model):
    """Redeemable shop item for Rust player points."""

    __tablename__ = "shared_db_rustshopitem"
    __table_args__ = (
        Index(
            "uq_rust_shop_enabled_name",
            "name",
            unique=True,
            postgresql_where=text("enabled IS TRUE"),
            sqlite_where=text("enabled = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    item_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RustSteamBindBonusAwarded(Model):
    """One-time Steam bind bonus per QQ user and per SteamID (survives unbind)."""

    __tablename__ = "shared_db_ruststeambindbonusawarded"
    __table_args__ = (
        UniqueConstraint("steam_id", name="uq_rust_steam_bind_bonus_steam_id"),
    )

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    steam_id: Mapped[str] = mapped_column(String(20), nullable=False)
    group_id: Mapped[str] = mapped_column(String(32), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RustCheckInRecord(Model):
    """Daily group check-in record."""

    __tablename__ = "shared_db_rustcheckinrecord"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    check_in_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    online_bonus_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class GroupSpecialTitleUsage(Model):
    """Daily usage counter for group special title self-service."""

    __tablename__ = "shared_db_groupspecialtitleusage"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    usage_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
