"""Shared media directory for protocol-side file:// video send."""

from __future__ import annotations

import sys
from pathlib import Path

# Linux / Docker：与常见 QQ 客户端数据目录对齐，便于与协议端同路径挂载。
_LINUX_DEFAULT = Path("/root/.config/QQ")
# Windows：落在机器草工作目录下的 data/tmp（Compose/Helm 已持久化 /app/data）。
_WINDOWS_DEFAULT = Path("data") / "tmp"


def default_shared_media_dir() -> Path:
    if sys.platform == "win32":
        return _WINDOWS_DEFAULT
    return _LINUX_DEFAULT


def resolve_shared_media_dir(configured: str | None) -> Path:
    """空配置走平台默认；非空则 expanduser，相对路径相对进程 cwd。"""
    raw = (configured or "").strip()
    if not raw:
        return default_shared_media_dir()
    return Path(raw).expanduser()
