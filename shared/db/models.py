"""Shared database models for cyxcbot Web Admin."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
        UniqueConstraint("dynamic_target_id", "group_id", name="uq_dynamic_target_group"),
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


class AuditLog(Model):
    """Audit trail for admin actions."""

    __tablename__ = "shared_db_auditlog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class SystemEvent(Model):
    """Important system events for operational visibility."""

    __tablename__ = "shared_db_systemevent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class LinkParserGroupPolicy(Model):
    """Per-group override for Bilibili link parser."""

    __tablename__ = "shared_db_linkparsergrouppolicy"

    group_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
